import { afterAll, describe, expect, it } from 'vitest';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import {
  collectCommitTrace,
  explicitTaskIds,
  mapCommits,
  parseCommitLog,
  traceabilityFindings
} from '../src/checks/commitMap.js';
import { checkTasks } from '../src/checks/tasks.js';
import { runReview } from '../src/engine.js';
import { diffFile, makeChange, makeDiff, task } from './helpers.js';

const SEP = '\u001e';
const F = '\u001f';

const dirs: string[] = [];
afterAll(() => {
  for (const d of dirs) rmSync(d, { recursive: true, force: true });
});

function gitRepo(): string {
  const dir = mkdtempSync(join(tmpdir(), 'stitcher-trace-'));
  dirs.push(dir);
  const git = (...args: string[]) =>
    execFileSync('git', args, {
      cwd: dir,
      encoding: 'utf8',
      env: {
        ...process.env,
        GIT_AUTHOR_NAME: 'fixture',
        GIT_AUTHOR_EMAIL: 'fixture@example.invalid',
        GIT_COMMITTER_NAME: 'fixture',
        GIT_COMMITTER_EMAIL: 'fixture@example.invalid'
      }
    });
  git('init', '-q');
  git('config', 'user.email', 'fixture@example.invalid');
  git('config', 'user.name', 'fixture');
  return dir;
}

function commit(root: string, message: string, path: string, content: string): string {
  mkdirSync(dirname(join(root, path)), { recursive: true });
  writeFileSync(join(root, path), content);
  execFileSync('git', ['add', path], { cwd: root });
  execFileSync('git', ['commit', '-q', '-m', message], { cwd: root });
  return execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim();
}

describe('Fixture A - orphan commit and orphan task are both reported', () => {
  it('parses git log records into sha/subject/files', () => {
    const raw =
      `${SEP}aaaaaaa1111${F}feat: refund ledger${F}body text${F}src/billing/refund.ts\n` +
      `src/billing/ledger.ts\n${SEP}bbbbbbb2222${F}docs: notes${F}${F}docs/notes.md\n`;
    const records = parseCommitLog(raw);
    expect(records).toHaveLength(2);
    expect(records[0].sha).toBe('aaaaaaa1111');
    expect(records[0].subject).toBe('feat: refund ledger');
    expect(records[0].files).toEqual(['src/billing/refund.ts', 'src/billing/ledger.ts']);
    expect(records[1].files).toEqual(['docs/notes.md']);
  });

  it('reports an orphan commit AND an orphan task, and not the mapped pair', () => {
    const change = makeChange({
      tasks: [
        task({ id: '1.1', text: 'Add refund ledger', done: true }),
        task({ id: '2.1', text: 'Export refunds', done: true })
      ]
    });
    const diff = makeDiff([
      diffFile('src/billing/rates.ts', ['export function rates() {}']),
      diffFile('src/billing/export.ts', ['export function exportRefunds() {}'])
    ]);
    const trace = {
      available: true,
      base: 'main',
      commits: [
        { sha: 'c0ffee1', subject: 'chore: tidy imports', body: '', files: ['src/billing/rates.ts'] },
        { sha: 'c0ffee2', subject: 'Task 2.1: add export', body: '', files: ['src/billing/export.ts'] }
      ]
    };

    const findings = traceabilityFindings(change, diff, trace);
    const orphanCommit = findings.filter((f) => f.checkId === 'trace-orphan-commit');
    const orphanTask = findings.filter((f) => f.checkId === 'trace-orphan-task');

    expect(orphanCommit).toHaveLength(1);
    expect(orphanCommit[0].message).toContain('c0ffee1');
    expect(orphanCommit[0].file).toBe('src/billing/rates.ts');
    expect(orphanTask).toHaveLength(1);
    expect(orphanTask[0].message).toContain('1.1');
    // The mapped pair (task 2.1 with commit c0ffee2) is not reported either way.
    expect(orphanCommit.some((f) => f.message.includes('c0ffee2'))).toBe(false);
    expect(orphanTask.some((f) => f.message.includes('2.1'))).toBe(false);
  });

  it('maps commits by explicit task id and by keyword fallback', () => {
    const change = makeChange({
      tasks: [task({ id: '1.1', text: 'Add refund ledger', done: true }), task({ id: '1.2', text: 'Export refunds' })]
    });
    const trace = {
      available: true,
      base: 'main',
      commits: [{ sha: 'abc1234', subject: 'feat: refund ledger export', body: 'Tasks #1.2', files: ['src/billing/x.ts'] }]
    };
    expect(explicitTaskIds(trace.commits[0], change.tasks)).toEqual(['1.2']);
    const mapping = mapCommits(trace, change.tasks);
    expect(mapping.commitToTasks.get('abc1234')).toContain('1.2');
  });

  it('an unavailable commit trace is a reported gap, never a silent clean mapping', () => {
    const change = makeChange({ tasks: [task({ id: '1.1', text: 'x', done: true })] });
    const findings = traceabilityFindings(change, makeDiff([]), {
      available: false,
      base: 'main',
      reason: 'not a git repository',
      commits: []
    });
    expect(findings.map((f) => f.checkId)).toContain('trace-commits-unavailable');
  });

  it('checkTasks wires the mapping (real git range)', async () => {
    const root = gitRepo();
    const base = commit(root, 'chore: initial', 'README.md', 'base\n');
    // One implementing commit, one behavior commit with no task reference.
    commit(root, 'Task 1.1: add refund ledger', 'src/billing/refund.ts', 'export const ledger = 1;\n');
    commit(root, 'chore: stray behavior', 'src/billing/audit.ts', 'export const audit = 2;\n');
    const diff = makeDiff([
      diffFile('src/billing/refund.ts', ['export const ledger = 1;']),
      diffFile('src/billing/audit.ts', ['export const audit = 2;'])
    ]);
    const change = makeChange({
      tasks: [task({ id: '1.1', text: 'Add refund ledger', done: true }), task({ id: '1.2', text: 'Add rates', done: true })]
    });
    const trace = await collectCommitTrace(root, base);
    expect(trace.available).toBe(true);
    const findings = checkTasks(change, diff, trace);
    expect(findings.some((f) => f.checkId === 'trace-orphan-commit')).toBe(true);
    // 1.1 is implemented; 1.2 is not.
    expect(findings.some((f) => f.checkId === 'trace-orphan-task' && f.message.includes('1.2'))).toBe(true);
    expect(findings.some((f) => f.checkId === 'trace-orphan-task' && f.message.includes('1.1'))).toBe(false);

    // The engine's real path computes the trace from root + base.
    const reviewed = await runReview(change, diff, '', { categories: new Set(['tasks']), root, base });
    expect(reviewed.findings.some((f) => f.checkId === 'trace-orphan-commit')).toBe(true);
  });
});
