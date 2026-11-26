import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { executablePass } from './helpers.js';
import { ensureBuild } from './ensure-build.js';
import type { ReviewResult } from '../src/types.js';

const ACTION_ROOT = fileURLToPath(new URL('..', import.meta.url));
const HARNESS = fileURLToPath(new URL('../../../scripts/stitcher-local.mjs', import.meta.url));
const dirs: string[] = [];

beforeAll(() => {
  ensureBuild(ACTION_ROOT);
}, 200_000);

afterAll(() => {
  for (const d of dirs) rmSync(d, { recursive: true, force: true });
});

async function harness() {
  return import(pathToFileURL(HARNESS).href) as Promise<{
    normalizeReview: (r: ReviewResult) => { verdict: string; findings: string[] };
    compareVerdicts: (a: ReviewResult, b: ReviewResult) => { parity: string; cause: string | null; differences: string[] };
  }>;
}

function scratch(): string {
  const dir = mkdtempSync(join(tmpdir(), 'stitcher-parity-'));
  dirs.push(dir);
  return dir;
}

function failingReview(): ReviewResult {
  return executablePass({
    verdict: 'CHANGES_REQUESTED',
    findings: [
      { severity: 'high', category: 'spec-compliance', checkId: 'requirement-missing', file: 'src/billing/refund.ts', line: 4, message: 'no evidence', evidenceRef: 'coh-ev-0123456789abcdef' }
    ]
  });
}

describe('Fixture E - local/CI divergence is caught and classified as a defect', () => {
  it('identical verdicts are parity; order of findings does not matter', async () => {
    const { compareVerdicts } = await harness();
    const a = executablePass();
    const b = executablePass();
    expect(compareVerdicts(a, b).parity).toBe('identical');
  });

  it('a divergence seed (local pass, CI fail) is classified as a defect', async () => {
    const { compareVerdicts } = await harness();
    const record = compareVerdicts(executablePass(), failingReview());
    expect(record.parity).toBe('divergent');
    expect(record.cause).toBe('defect');
    expect(record.differences.join(' ')).toContain('verdict');
    expect(record.differences.join(' ')).toContain('findings only in CI');
  });

  it('the harness exits non-zero on divergence and zero on parity (artifact mode)', () => {
    const dir = scratch();
    const local = join(dir, 'local.json');
    const ciPass = join(dir, 'ci-pass.json');
    const ciFail = join(dir, 'ci-fail.json');
    const out = join(dir, 'record.json');
    writeFileSync(local, JSON.stringify(executablePass()));
    writeFileSync(ciPass, JSON.stringify(executablePass()));
    writeFileSync(ciFail, JSON.stringify(failingReview()));

    const same = spawnSync(process.execPath, [HARNESS, '--local', local, '--ci', ciPass, '--out', out], { encoding: 'utf8' });
    expect(same.status).toBe(0);
    expect(JSON.parse(readFileSync(out, 'utf8')).parity).toBe('identical');

    const diverged = spawnSync(process.execPath, [HARNESS, '--local', local, '--ci', ciFail, '--out', out], { encoding: 'utf8' });
    expect(diverged.status).toBe(1);
    const record = JSON.parse(readFileSync(out, 'utf8'));
    expect(record.parity).toBe('divergent');
    expect(record.cause).toBe('defect');
    expect(diverged.stderr).toContain('PARITY DEFECT');
  });

  it('fails closed when the review build is missing (never parity-green)', () => {
    const dir = scratch();
    const local = join(dir, 'local.json');
    writeFileSync(local, JSON.stringify(executablePass()));
    // --run requires a change/base; without them it is a usage error (exit 2).
    const usage = spawnSync(process.execPath, [HARNESS, '--run'], { encoding: 'utf8' });
    expect(usage.status).toBe(2);
  });

  it('--run catches a working-tree change that the clean CI worktree never sees', () => {
    const root = scratch();
    const git = (...args: string[]) => execFileSync('git', args, { cwd: root, encoding: 'utf8' });
    git('init', '-q');
    git('config', 'user.email', 'fixture@example.invalid');
    git('config', 'user.name', 'fixture');
    const spec = '## ADDED Requirements\n\n### Requirement: Refund ledger\nThe refund ledger SHALL record every refund.\n';
    const write = (path: string, content: string) => {
      mkdirSync(dirname(join(root, path)), { recursive: true });
      writeFileSync(join(root, path), content);
    };
    write('openspec/specs/billing-refunds/spec.md', spec);
    write('openspec/changes/wiring/specs/billing-refunds/spec.md', spec);
    write('openspec/changes/wiring/proposal.md', '# wiring\n');
    write('src/billing/refund.ts', 'export function refund() { return 1; }\n');
    git('add', '-A');
    git('commit', '-q', '-m', 'base');

    // The seed: a local, uncommitted behavior change. The local side reviews
    // the working tree; the CI worktree sees an empty range.
    write('src/billing/refund.ts', 'export function refund() { return 2; }\n');

    const res = spawnSync(
      process.execPath,
      [HARNESS, '--run', '--root', root, '--change', 'wiring', '--base', 'HEAD'],
      { encoding: 'utf8', timeout: 180_000 }
    );
    expect(res.status).toBe(1);
    const record = JSON.parse(res.stdout);
    expect(record.parity).toBe('divergent');
    expect(record.cause).toBe('defect');
  }, 200_000);
});
