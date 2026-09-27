import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { Diff, DiffFile } from '../types.js';

const exec = promisify(execFile);

/** Large monorepo/whole-tree diffs (800k+ lines observed) need a big buffer. */
const GIT_MAX_BUFFER = 128 * 1024 * 1024;

/** Error thrown when the git binary itself is unavailable — never treat as an empty diff. */
export class GitMissingError extends Error {
  constructor() {
    super('git executable not found in PATH — cannot diff the repository (install git or fix PATH)');
    this.name = 'GitMissingError';
  }
}

function runGit(args: string[], cwd: string, timeout = 30_000): Promise<string> {
  return exec('git', args, { cwd, maxBuffer: GIT_MAX_BUFFER, timeout }).then(
    (r) => r.stdout,
    (e) => {
      if ((e as NodeJS.ErrnoException).code === 'ENOENT') throw new GitMissingError();
      throw new Error(`git ${args.join(' ')} failed: ${(e as Error).message}`);
    }
  );
}

/** Re-throw infrastructure failures (git missing); only ref-resolution misses fall through. */
function isMissing(err: unknown): boolean {
  return err instanceof GitMissingError;
}

/**
 * Resolve a base ref for the range diff. CI checkouts (detached HEAD, no
 * local branches) resolve through remote-tracking refs; local branches keep
 * priority. Returns null when nothing resolves (caller falls back).
 */
export async function resolveBase(projectRoot: string, base: string): Promise<string | null> {
  // Already a full ref or SHA — use directly.
  if (/^[0-9a-f]{4,40}$/i.test(base) || base.includes('/') || base.startsWith('HEAD')) {
    for (const cand of [base, `origin/${base.replace(/^origin\//, '')}`]) {
      try {
        await runGit(['rev-parse', '--verify', '--quiet', cand], projectRoot);
        return cand;
      } catch (err) {
        if (isMissing(err)) throw err;
      }
    }
  }
  for (const cand of [base, `origin/${base}`, `upstream/${base}`, `remotes/origin/${base}`]) {
    try {
      await runGit(['rev-parse', '--verify', '--quiet', cand], projectRoot);
      return cand;
    } catch (err) {
      if (isMissing(err)) throw err;
      // try next candidate
    }
  }
  return null;
}

/**
 * Get unified diff with zero context lines suppressed — we use --unified=3
 * plus name-status to detect renames/new files.
 */
export async function getDiff(projectRoot: string, base: string): Promise<Diff> {
  // Ensure base resolves; support "HEAD~1", "main", "origin/main"
  const ref = await resolveBase(projectRoot, base);
  if (ref) {
    try {
      const ranged = parseUnifiedDiff(
        await runGit(['diff', `${ref}...HEAD`, '--unified=3', '--no-color', '--no-ext-diff'], projectRoot)
      );
      // Empty range (base==HEAD, or nothing committed yet on top of base):
      // review the working tree so local iteration still works.
      if (ranged.files.length > 0) return withUntracked(projectRoot, ranged);
    } catch (err) {
      if (isMissing(err)) throw err;
      // A failed range diff must never silently degrade the review — say why.
      console.error(`stitcher-codereview: warning: range diff ${ref}...HEAD failed (${(err as Error).message}); falling back to the working tree.`);
    }
  }
  try {
    const raw = await runGit(['diff', 'HEAD', '--unified=3', '--no-color', '--no-ext-diff'], projectRoot);
    return await withUntracked(projectRoot, parseUnifiedDiff(raw));
  } catch (err) {
    if (isMissing(err)) throw err;
    return { files: [], addedText: '', evidenceText: '' };
  }
}

/**
 * Diff two arbitrary refs (from...to) without touching the working tree.
 * Used by serve mode: from = base sha, to = locally-fetched PR/MR head ref.
 */
export async function getDiffRange(projectRoot: string, from: string, to: string): Promise<Diff> {
  try {
    const raw = await runGit(['diff', `${from}...${to}`, '--unified=3', '--no-color', '--no-ext-diff'], projectRoot);
    return parseUnifiedDiff(raw);
  } catch (err) {
    if (isMissing(err)) throw err;
    return { files: [], addedText: '', evidenceText: '' };
  }
}

/** Untracked, unignored files (git status ??) never appear in diffs — read them in (bounded). */
async function withUntracked(projectRoot: string, diff: Diff): Promise<Diff> {
  let status: string;
  try {
    status = await runGit(['status', '--porcelain=v1', '-z', '--untracked-files=all'], projectRoot, 15_000);
  } catch {
    return diff;
  }
  const fresh = status.split('\0').filter(Boolean).filter((e) => e.startsWith('?? ')).map((e) => e.slice(3)).slice(0, 500);
  if (fresh.length === 0) return diff;
  const files = [...diff.files];
  const { stat } = await import('node:fs/promises');
  for (const p of fresh) {
    if (files.some((f) => f.path === p)) continue;
    const entry: DiffFile = { path: p, addedLines: [], removedLines: [], hunks: [], isNew: true, isDeleted: false };
    try {
      const st = await stat(join(projectRoot, p)).catch(() => null);
      if (st && st.size > 256 * 1024) continue; // skip large untracked binaries
      const content = await readFile(join(projectRoot, p), 'utf8');
      if (!content.includes('\0')) {
        const capped = content.length > 256 * 1024 ? content.slice(0, 256 * 1024) : content;
        entry.addedLines = capped.split('\n').map((text, i) => ({ n: i + 1, text }));
      }
    } catch {
      // unreadable — keep the path-only entry so path checks still see it
    }
    files.push(entry);
  }
  return { files, ...buildTexts(files) };
}

function buildTexts(files: DiffFile[]): Pick<Diff, 'addedText' | 'evidenceText'> {
  const addedText = files.flatMap((f) => f.addedLines.map((l) => l.text)).join('\n');
  // Evidence matching ignores generated/noise content (lockfiles, bundles)
  // and openspec meta files (writing a spec is not implementing it);
  // stats still count every file.
  const evidenceText = files
    .filter((f) => !/(^|\/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|bun\.lockb)$/.test(f.path))
    .filter((f) => !/(^|\/)(dist|build|coverage)\//.test(f.path))
    .filter((f) => !/^openspec\//.test(f.path))
    .filter((f) => !/\.min\.js$/.test(f.path))
    .flatMap((f) => f.addedLines.map((l) => l.text))
    .join('\n');
  return { addedText, evidenceText };
}

export function parseUnifiedDiff(raw: string): Diff {
  const files: DiffFile[] = [];
  const chunks = raw.split(/^diff --git /m).filter(Boolean);
  for (const c of chunks) {
    const lines = c.split('\n');
    const header = lines[0] ?? '';
    const m = header.match(/[ab]\/(.+?) (?:[ab]\/(.+))?$/);
    const path = (m?.[2] ?? m?.[1] ?? header).trim();
    const isNew = /new file mode/.test(c);
    const isDeleted = /deleted file mode/.test(c);
    const addedLines: DiffFile['addedLines'] = [];
    const removedLines: DiffFile['removedLines'] = [];
    const hunks: string[] = [];
    let newLine = 0;
    for (const l of lines) {
      const h = l.match(/^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
      if (h) {
        newLine = parseInt(h[1], 10);
        hunks.push(l);
        continue;
      }
      if (l.startsWith('+') && !l.startsWith('+++')) {
        addedLines.push({ n: newLine++, text: l.slice(1) });
      } else if (l.startsWith('-') && !l.startsWith('---')) {
        removedLines.push({ n: 0, text: l.slice(1) });
      } else if (l.startsWith(' ')) {
        newLine++;
      }
    }
    if (path && path !== '/dev/null') {
      files.push({ path, addedLines, removedLines, hunks, isNew, isDeleted });
    }
  }
  const { addedText, evidenceText } = buildTexts(files);
  return { files, addedText, evidenceText };
}
