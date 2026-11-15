import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { checkReverseDrift, specTouchedCapabilities } from '../src/checks/drift.js';
import { baselineSpec, diffFile, makeDiff, requirement } from './helpers.js';
import { ensureBuild } from './ensure-build.js';

const ACTION_ROOT = fileURLToPath(new URL('..', import.meta.url));
const REPO_ROOT = join(ACTION_ROOT, '..', '..');
const GATE = join(REPO_ROOT, 'scripts', 'stitcher-drift.mjs');
const dirs: string[] = [];

beforeAll(() => {
  // The gate shells to the built CLI: build once so the test exercises the
  // real execution path, not a mock of it.
  ensureBuild(ACTION_ROOT);
}, 200_000);

function repo(): string {
  const dir = mkdtempSync(join(tmpdir(), 'stitcher-drift-'));
  dirs.push(dir);
  execFileSync('git', ['init', '-q'], { cwd: dir });
  execFileSync('git', ['config', 'user.email', 'fixture@example.invalid'], { cwd: dir });
  execFileSync('git', ['config', 'user.name', 'fixture'], { cwd: dir });
  return dir;
}

function write(root: string, path: string, content: string): void {
  mkdirSync(dirname(join(root, path)), { recursive: true });
  writeFileSync(join(root, path), content);
}

function commit(root: string, message: string): string {
  execFileSync('git', ['add', '-A'], { cwd: root });
  execFileSync('git', ['commit', '-q', '-m', message], { cwd: root });
  return execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim();
}

const SPEC = [
  '## ADDED Requirements',
  '',
  '### Requirement: Refund ledger',
  'The refund ledger SHALL record every refund.',
  ''
].join('\n');

describe('Fixture C - a silent behavior change is a reverse-drift finding', () => {
  it('flags a changed behavior file when no spec was updated in range', () => {
    const baseline = [baselineSpec('billing-refunds', [
      requirement({ id: 'Refund ledger', capability: 'billing-refunds', text: 'SHALL record every refund' })
    ])];
    const diff = makeDiff([diffFile('src/billing/refund.ts', ['export function refund() { return 1; }'])]);

    const findings = checkReverseDrift(baseline, diff);
    expect(findings).toHaveLength(1);
    expect(findings[0].checkId).toBe('drift-uncovered');
    expect(findings[0].severity).toBe('medium');
    expect(findings[0].file).toBe('src/billing/refund.ts');
    // Names the behavior (capability), not just the file.
    expect(findings[0].message).toContain('billing-refunds');
  });

  it('is specific: a spec update in the same range covers the capability', () => {
    const baseline = [baselineSpec('billing-refunds', [
      requirement({ id: 'Refund ledger', capability: 'billing-refunds', text: 'SHALL record every refund' })
    ])];
    const diff = makeDiff([
      diffFile('src/billing/refund.ts', ['export function refund() { return 1; }']),
      diffFile('openspec/specs/billing-refunds/spec.md', ['The refund ledger SHALL record every refund.'])
    ]);
    expect(specTouchedCapabilities(diff).has('billing-refunds')).toBe(true);
    expect(checkReverseDrift(baseline, diff).some((f) => f.checkId === 'drift-uncovered')).toBe(false);
  });

  it('reports an unmapped file at low severity instead of staying silent', () => {
    const baseline = [baselineSpec('billing-refunds', [
      requirement({ id: 'Refund ledger', capability: 'billing-refunds', text: 'SHALL record every refund' })
    ])];
    const findings = checkReverseDrift(baseline, makeDiff([diffFile('src/zzz/qqq.ts', ['export const q = 1;'])]));
    expect(findings[0].checkId).toBe('drift-uncategorized');
    expect(findings[0].severity).toBe('low');
  });

  it('runs from the repo gate: a seeded silent change reds the gate, a specified one passes', () => {
    const drift = repo();
    write(drift, 'openspec/specs/billing-refunds/spec.md', SPEC);
    write(drift, 'src/billing/refund.ts', 'export function refund() { return 1; }\n');
    const base = commit(drift, 'base');
    write(drift, 'src/billing/refund.ts', 'export function refund() { return 2; }\n');
    commit(drift, 'silent behavior change');

    const failed = spawnGate(drift, base);
    expect(failed.status).toBe(1);
    const parsed = JSON.parse(failed.stdout);
    expect(parsed.findings.some((f: { checkId: string }) => f.checkId === 'drift-uncovered')).toBe(true);

    const covered = repo();
    write(covered, 'openspec/specs/billing-refunds/spec.md', SPEC);
    write(covered, 'src/billing/refund.ts', 'export function refund() { return 1; }\n');
    const coveredBase = commit(covered, 'base');
    write(covered, 'src/billing/refund.ts', 'export function refund() { return 2; }\n');
    write(covered, 'openspec/specs/billing-refunds/spec.md', `${SPEC}\nUpdated: refunds record the amount.\n`);
    commit(covered, 'behavior change with spec update');

    const passed = spawnGate(covered, coveredBase);
    expect(passed.status).toBe(0);
    expect(JSON.parse(passed.stdout).findings.some((f: { checkId: string }) => f.checkId === 'drift-uncovered')).toBe(false);
  }, 120_000);

  function spawnGate(root: string, base: string): { status: number | null; stdout: string } {
    const res = spawnSync(
      process.execPath,
      [GATE, '--base', base, '--root', root, '--fail-on', 'medium', '--format', 'json'],
      { encoding: 'utf8', timeout: 120_000 }
    );
    return { status: res.status, stdout: res.stdout ?? '' };
  }
});

afterAll(() => {
  for (const d of dirs) rmSync(d, { recursive: true, force: true });
});
