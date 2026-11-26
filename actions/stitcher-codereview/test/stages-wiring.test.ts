import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { execFileSync, spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { BUILTIN_TOOLS } from '../src/checks/external-tools.js';
import { ensureBuild } from './ensure-build.js';

const ACTION_ROOT = fileURLToPath(new URL('..', import.meta.url));
const REPO_ROOT = join(ACTION_ROOT, '..', '..');
const CLI = join(ACTION_ROOT, 'dist', 'cli.js');
const dirs: string[] = [];

beforeAll(() => {
  ensureBuild(ACTION_ROOT);
}, 200_000);

afterAll(() => {
  for (const d of dirs) rmSync(d, { recursive: true, force: true });
});

function scratchRepo(): string {
  const dir = mkdtempSync(join(tmpdir(), 'stitcher-wiring-'));
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

function cli(args: string[], cwd: string) {
  return spawnSync(process.execPath, [CLI, ...args, '--no-user-config'], {
    cwd,
    encoding: 'utf8',
    timeout: 120_000,
    env: { ...process.env, STITCHER_CODEREVIEW_NO_USER_CONFIG: '1' }
  });
}

const SPEC = '## ADDED Requirements\n\n### Requirement: Refund ledger\nThe refund ledger SHALL record every refund.\n';

describe('Stage wiring - whole-repo mode, drift gate, verdict endpoint, hook file', () => {
  it('--scan repository runs on the whole tree with no --change', () => {
    const root = scratchRepo();
    write(root, 'openspec/specs/billing-refunds/spec.md', SPEC);
    write(root, 'src/billing/refund.ts', 'export function refund() { return 1; }\n');
    commit(root, 'base');

    const res = cli(['--root', root, '--scan', 'repository', '--format', 'json', '--fail-on', 'high'], root);
    expect(res.status).toBe(0);
    const parsed = JSON.parse(res.stdout);
    expect(parsed.change).toBe('repository-scan');
    expect(parsed.verdict).toBeDefined();
    // Non-vacuous: the scan actually classified the capability.
    expect(parsed.findings.some((f: { checkId: string }) => f.checkId === 'scan-capability-drift')).toBe(true);
  }, 120_000);

  it('--verdict emits a promote/halt record keyed to the subject digest', () => {
    const root = scratchRepo();
    write(root, 'openspec/specs/billing-refunds/spec.md', SPEC);
    write(root, 'src/billing/refund.ts', 'export function refund() { return 1; }\n');
    const base = commit(root, 'base');
    write(root, 'openspec/changes/wiring/specs/billing-refunds/spec.md', SPEC);
    write(root, 'openspec/changes/wiring/proposal.md', '# wiring\n');
    write(root, 'src/billing/refund.ts', 'export function refund() { return 2; }\n');
    commit(root, 'behavior change');

    const digest = 'd'.repeat(64);
    const res = cli(
      ['--root', root, '--change', 'wiring', '--base', base, '--verdict',
        '--subject-digest', digest, '--producer', 'claude-code-loop',
        '--loop-outputs', digest, '--format', 'json'],
      root
    );
    expect(res.status).toBe(1);
    const record = JSON.parse(res.stdout);
    expect(record.verdict).toBe('halt');
    expect(record.subjectDigest).toBe(digest);
    expect(record.verification).toBe('UNKNOWN');
    expect(record.reasons).toContain('loop-self-certification');
  }, 120_000);

  it('the CLI exposes the stage flags', () => {
    const res = spawnSync(process.execPath, [CLI, '--help'], { encoding: 'utf8' });
    for (const flag of ['--scan', '--drift-only', '--verdict', '--subject-digest', '--evidence-base-url']) {
      expect(res.stdout).toContain(flag);
    }
  });

  it('ships the pre-commit hook contract', () => {
    const hooks = readFileSync(join(REPO_ROOT, '.pre-commit-hooks.yaml'), 'utf8');
    expect(hooks).toContain('id: stitcher-codereview');
    expect(hooks).toContain('language:');
    expect(hooks).toContain('pass_filenames: false');
    expect(existsSync(join(REPO_ROOT, 'scripts', 'stitcher-local.mjs'))).toBe(true);
    expect(existsSync(join(REPO_ROOT, 'scripts', 'stitcher-drift.mjs'))).toBe(true);
  });

  it('registers the Q12.2 adapter targets with source identity', () => {
    expect(BUILTIN_TOOLS['guardrails-scan'].displayName).toBe('guardrails-scan.mjs');
    expect(BUILTIN_TOOLS['secret-scan-declared'].displayName).toBe('secret-scan-declared.sh');
    expect(BUILTIN_TOOLS['guardrails-scan'].versionFromFile).toBe('scripts/guardrails-scan.mjs');
  });
});
