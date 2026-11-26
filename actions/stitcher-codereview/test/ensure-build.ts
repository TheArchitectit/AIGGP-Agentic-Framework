import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readdirSync, rmSync, statSync } from 'node:fs';
import { join } from 'node:path';

/**
 * Build the CLI once per test run, safely under the repo's per-file runner.
 *
 * `scripts/run-tests.mjs` spawns each vitest file in its own process (pool up
 * to 8), so several suites can reach this at the same time. A lock directory
 * serializes the build and the freshness check runs again under the lock, so a
 * process that waited does not rebuild what another just produced. In CI the
 * workflow builds before the runner starts, so the freshness check usually
 * skips the work entirely.
 */
export function ensureBuild(actionRoot: string): void {
  const dist = join(actionRoot, 'dist', 'cli.js');
  if (isFresh(actionRoot, dist)) return;
  const lock = join(actionRoot, 'dist', '.build-lock');
  mkdirSync(join(actionRoot, 'dist'), { recursive: true });
  let held = false;
  for (let i = 0; i < 300; i++) {
    try {
      mkdirSync(lock);
      held = true;
      break;
    } catch {
      execFileSync('sleep', ['0.05']);
    }
  }
  if (!held) throw new Error('ensureBuild: could not acquire the build lock');
  try {
    if (isFresh(actionRoot, dist)) return;
    execFileSync('npm', ['run', 'build'], { cwd: actionRoot, stdio: 'pipe', timeout: 180_000 });
  } finally {
    rmSync(lock, { recursive: true, force: true });
  }
}

function isFresh(actionRoot: string, distCli: string): boolean {
  if (!existsSync(distCli)) return false;
  const built = statSync(distCli).mtimeMs;
  return newestMtime(join(actionRoot, 'src')) <= built;
}

function newestMtime(dir: string): number {
  let newest = 0;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) newest = Math.max(newest, newestMtime(full));
    else if (entry.name.endsWith('.ts')) newest = Math.max(newest, statSync(full).mtimeMs);
  }
  return newest;
}
