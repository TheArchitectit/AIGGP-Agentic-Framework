import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import type { Diff, Finding, OpenSpecChange, TaskItem } from '../types.js';
import { keywords } from '../spec/parser.js';
import { isDriftRelevant } from './drift.js';

const exec = promisify(execFile);
const COMMIT_MAX_BUFFER = 64 * 1024 * 1024;

/** One commit as traceability sees it: identity, message, touched files. */
export interface CommitRecord {
  sha: string;
  subject: string;
  body: string;
  files: string[];
}

/** Result of asking git for the commits in a range. `available:false` is a gap, not silence. */
export interface CommitTrace {
  available: boolean;
  commits: CommitRecord[];
  base: string;
  reason?: string;
}

const RECORD_SEP = '\u001e';
const FIELD_SEP = '\u001f';

/**
 * Parse `git log --name-only --format=%x1e%H%x1f%s%x1f%b%x1f` output.
 * Exported so the mapping contract is testable without a repository.
 */
export function parseCommitLog(raw: string): CommitRecord[] {
  const out: CommitRecord[] = [];
  for (const chunk of raw.split(RECORD_SEP)) {
    if (!chunk.trim()) continue;
    const parts = chunk.split(FIELD_SEP);
    if (parts.length < 3) continue;
    const sha = (parts[0] ?? '').trim();
    if (!/^[0-9a-f]{7,64}$/i.test(sha)) continue;
    const subject = (parts[1] ?? '').trim();
    const body = (parts[2] ?? '').trim();
    const files = parts
      .slice(3)
      .join(FIELD_SEP)
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean);
    out.push({ sha, subject, body, files });
  }
  return out;
}

/**
 * Collect the commits in `base...HEAD`. Fail-open to `available:false` with a
 * reason: a traceability run that cannot see git must say so, never report a
 * clean mapping it did not compute.
 */
export async function collectCommitTrace(root: string, base: string): Promise<CommitTrace> {
  try {
    const { stdout } = await exec(
      'git',
      ['log', `--format=${RECORD_SEP}%H${FIELD_SEP}%s${FIELD_SEP}%b${FIELD_SEP}`, '--name-only', `${base}...HEAD`],
      { cwd: root, maxBuffer: COMMIT_MAX_BUFFER, timeout: 30_000 }
    );
    return { available: true, commits: parseCommitLog(stdout), base };
  } catch (err) {
    return {
      available: false,
      commits: [],
      base,
      reason: (err as Error)?.message ?? String(err)
    };
  }
}

/** Task ids a commit message names. Only ids that exist in tasks.md are kept. */
export function explicitTaskIds(record: CommitRecord, tasks: TaskItem[]): string[] {
  const text = `${record.subject}\n${record.body}`;
  const candidates = new Set<string>();
  for (const m of text.matchAll(/\b(?:tasks?|tasks\.md)\s*#?\s*(\d+(?:\.\d+)*)\b/gi)) {
    candidates.add(m[1]);
  }
  for (const m of text.matchAll(/\[(\d+(?:\.\d+)*)\]/g)) {
    candidates.add(m[1]);
  }
  for (const m of text.matchAll(/\b(\d+\.\d+)\b/g)) {
    candidates.add(m[1]);
  }
  const known = new Set(tasks.map((t) => t.id));
  return [...candidates].filter((id) => known.has(id));
}

/** Keyword-overlap fallback for commits that do not name a task id. */
function keywordMappedTasks(record: CommitRecord, tasks: TaskItem[]): string[] {
  const hay = `${record.subject} ${record.body} ${record.files.join(' ')}`.toLowerCase();
  const ids: string[] = [];
  for (const t of tasks) {
    const keys = [...keywords(t.text)];
    if (keys.length === 0) continue;
    const hits = keys.filter((k) => hay.includes(k)).length;
    if (hits / keys.length >= 0.25) ids.push(t.id);
  }
  return ids;
}

export interface CommitMapping {
  /** commit sha -> task ids it implements. */
  commitToTasks: Map<string, string[]>;
  /** task id -> commit shas implementing it. */
  taskToCommits: Map<string, string[]>;
}

export function mapCommits(trace: CommitTrace, tasks: TaskItem[]): CommitMapping {
  const commitToTasks = new Map<string, string[]>();
  const taskToCommits = new Map<string, string[]>();
  for (const t of tasks) taskToCommits.set(t.id, []);
  for (const record of trace.commits) {
    const explicit = explicitTaskIds(record, tasks);
    const ids = explicit.length > 0 ? explicit : keywordMappedTasks(record, tasks);
    commitToTasks.set(record.sha, ids);
    for (const id of ids) taskToCommits.get(id)?.push(record.sha);
  }
  return { commitToTasks, taskToCommits };
}

function shortSha(sha: string): string {
  return sha.slice(0, 12);
}

/**
 * Bidirectional traceability findings. Both directions are reported:
 *  - a commit touching behavior that maps to no task is an orphan commit;
 *  - a task marked done that no commit implements is an orphan task.
 */
export function traceabilityFindings(
  change: OpenSpecChange,
  diff: Diff,
  trace: CommitTrace
): Finding[] {
  const findings: Finding[] = [];
  if (!trace.available) {
    findings.push({
      severity: 'info',
      category: 'tasks',
      checkId: 'trace-commits-unavailable',
      message:
        `Commit mapping unavailable for base \`${trace.base}\`` +
        `${trace.reason ? `: ${trace.reason}` : ''} — only the task side of traceability ran.`,
      suggestion: 'Run with a resolvable --base and a full (non-shallow) checkout to map commits to tasks.'
    });
    return findings;
  }
  if (change.tasks.length === 0) return findings;

  const { commitToTasks, taskToCommits } = mapCommits(trace, change.tasks);
  const changed = new Set(diff.files.map((f) => f.path));

  for (const record of trace.commits) {
    const ids = commitToTasks.get(record.sha) ?? [];
    if (ids.length > 0) continue;
    const relevant = record.files.filter((p) => isDriftRelevant(p) && changed.has(p));
    if (relevant.length === 0) continue;
    findings.push({
      severity: 'medium',
      category: 'tasks',
      checkId: 'trace-orphan-commit',
      file: relevant[0],
      message:
        `Commit ${shortSha(record.sha)} ("${record.subject.slice(0, 100)}") changes ` +
        `${relevant.length} behavior file(s) (e.g. ${relevant.slice(0, 3).join(', ')}) ` +
        'but maps to no task in tasks.md.',
      suggestion: 'Reference the task id in the commit message (e.g. "Task 1.2: ...") or add a task for this change.'
    });
  }

  for (const t of change.tasks) {
    if (!t.done) continue;
    if ((taskToCommits.get(t.id) ?? []).length > 0) continue;
    findings.push({
      severity: 'medium',
      category: 'tasks',
      checkId: 'trace-orphan-task',
      message: `Task ${t.id} [x] "${t.text.slice(0, 100)}" is marked complete but no commit implements it.`,
      suggestion: 'Uncheck the task, or land the implementing commit and name the task id in its message.'
    });
  }

  return findings;
}
