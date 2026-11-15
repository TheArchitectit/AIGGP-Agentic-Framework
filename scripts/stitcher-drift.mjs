#!/usr/bin/env node
/**
 * stitcher-drift.mjs - the repo-level reverse-drift gate (aiggp-08 Stage 3).
 *
 * Runs the vendored stitcher's `--drift-only` mode: every changed behavior file
 * whose capability gained no spec update in the same range is a finding, at the
 * severity the bundle declares. Wraps the built CLI so CI and pre-commit run
 * the same code path instead of a second implementation.
 *
 *   node scripts/stitcher-drift.mjs --base <ref> [--root DIR] [--change NAME]
 *        [--fail-on medium] [--format json] [--severity medium]
 *
 * Exit: 0 no findings at/above --fail-on, 1 findings at/above, 2 usage or a
 * missing build (fail closed - "could not evaluate" is never a pass).
 */
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const CLI = resolve(HERE, '..', 'actions', 'stitcher-codereview', 'dist', 'cli.js');

function parseArgs(argv) {
	const opts = { root: '.', format: 'json', 'fail-on': 'medium', severity: 'medium' };
	for (let i = 0; i < argv.length; i++) {
		const a = argv[i];
		if (a === '--help' || a === '-h') return { help: true };
		if (!a.startsWith('--')) {
			console.error(`stitcher-drift: unexpected argument: ${a}`);
			return { usage: true };
		}
		const key = a.slice(2);
		const val = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : 'true';
		opts[key] = val;
	}
	return opts;
}

function usage() {
	console.error('usage: node scripts/stitcher-drift.mjs --base <ref> [--root DIR] [--change NAME] [--fail-on medium] [--format json] [--severity medium]');
}

const opts = parseArgs(process.argv.slice(2));
if (opts.help) {
	usage();
	process.exit(0);
}
if (opts.usage || (!opts.base && !opts.help)) {
	usage();
	process.exit(2);
}
if (!existsSync(CLI)) {
	console.error(`stitcher-drift: ${CLI} is missing - run "npm run build" in actions/stitcher-codereview first.`);
	process.exit(2);
}

const args = [CLI, '--root', resolve(opts.root), '--base', opts.base, '--drift-only',
	'--drift-severity', opts.severity, '--fail-on', opts['fail-on'], '--format', opts.format, '--no-user-config'];
if (opts.change) args.push('--change', opts.change);

// Non-vacuity: the gate names its scope before it evaluates anything.
console.error(`[stitcher-drift] scope: base=${opts.base} root=${resolve(opts.root)} change=${opts.change ?? '(none - range derived)'}`);

const res = spawnSync(process.execPath, args, {
	cwd: resolve(opts.root),
	encoding: 'utf8',
	timeout: 300_000,
	maxBuffer: 64 * 1024 * 1024
});
if (res.stdout) process.stdout.write(res.stdout);
if (res.stderr) process.stderr.write(res.stderr);
if (res.status !== 0 && res.status !== 1) {
	console.error(`stitcher-drift: the gate could not evaluate the range (exit ${res.status}).`);
	process.exit(2);
}
process.exit(res.status ?? 2);
