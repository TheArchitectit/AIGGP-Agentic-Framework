#!/usr/bin/env node
/**
 * stitcher-local.mjs - local/CI parity harness for the vendored stitcher review
 * (aiggp-08 Stage 4: "Pre-commit execution SHALL use the same images and
 * scripts as CI and SHALL produce identical verdicts for the same change").
 *
 * Two modes:
 *
 *   artifact compare (no side effects):
 *     node scripts/stitcher-local.mjs --local local.json --ci ci.json [--out parity.json]
 *   run both sides from one tree (local working tree vs a clean worktree at HEAD):
 *     node scripts/stitcher-local.mjs --run --root . --change <name> --base <ref> [--ci-root DIR]
 *
 * A divergent verdict is classified as a DEFECT and exits 1: the parity
 * fixture fails until the divergence is fixed (reviewer-surfaces spec).
 * A missing build fails closed (exit 2) - it is never "parity green".
 *
 * Exports normalizeReview/compareVerdicts so the parity contract is unit
 * testable without spawning a review.
 */
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(HERE, '..');
const CLI = join(REPO_ROOT, 'actions', 'stitcher-codereview', 'dist', 'cli.js');

function findingKey(f) {
	return [f.checkId, f.file ?? '', f.line ?? 0, f.severity].join('\u0000');
}

function coverageKey(c) {
	return [c.requirementId, c.capability, c.status].join('\u0000');
}

/** Normalize one review JSON into the comparable surface. */
export function normalizeReview(result) {
	const findings = [...(result.findings ?? [])].map(findingKey).sort();
	const coverage = [...(result.requirementCoverage ?? [])].map(coverageKey).sort();
	return {
		verdict: result.verdict ?? 'UNKNOWN',
		subjectDigest:
			result.verification?.fingerprint?.touchedHash ??
			result.verification?.fingerprint?.head ??
			null,
		findings,
		coverage,
		stats: {
			filesChanged: result.stats?.filesChanged ?? 0,
			requirementsCovered: result.stats?.requirementsCovered ?? 0,
			requirementsTotal: result.stats?.requirementsTotal ?? 0
		}
	};
}

/**
 * Compare the local and CI verdicts. Any difference in verdict, findings or
 * requirement coverage is a divergence, and a divergence is a defect by
 * definition (the same change must produce the same verdict).
 */
export function compareVerdicts(localResult, ciResult) {
	const local = normalizeReview(localResult);
	const ci = normalizeReview(ciResult);
	const differences = [];
	if (local.verdict !== ci.verdict) differences.push(`verdict: local=${local.verdict} ci=${ci.verdict}`);
	const onlyLocal = local.findings.filter((k) => !ci.findings.includes(k));
	const onlyCi = ci.findings.filter((k) => !local.findings.includes(k));
	if (onlyLocal.length) differences.push(`findings only in local: ${onlyLocal.length}`);
	if (onlyCi.length) differences.push(`findings only in CI: ${onlyCi.length}`);
	const covLocal = local.coverage.filter((k) => !ci.coverage.includes(k));
	const covCi = ci.coverage.filter((k) => !local.coverage.includes(k));
	if (covLocal.length || covCi.length) differences.push('requirement coverage differs');
	if (local.subjectDigest && ci.subjectDigest && local.subjectDigest !== ci.subjectDigest) {
		differences.push(`subject digest: local=${local.subjectDigest} ci=${ci.subjectDigest}`);
	}
	return {
		parity: differences.length === 0 ? 'identical' : 'divergent',
		// Spec: a divergent local/CI verdict is classified as a defect.
		cause: differences.length === 0 ? null : 'defect',
		differences,
		local,
		ci
	};
}

function readJson(path) {
	try {
		return JSON.parse(readFileSync(path, 'utf8'));
	} catch (err) {
		console.error(`stitcher-local: cannot read ${path}: ${err.message}`);
		process.exit(2);
	}
}

function runCli(root, change, base) {
	if (!existsSync(CLI)) {
		console.error(`stitcher-local: ${CLI} is missing - run "npm run build" in actions/stitcher-codereview first (fail closed).`);
		process.exit(2);
	}
	const res = spawnSync(
		process.execPath,
		[CLI, '--root', root, '--change', change, '--base', base, '--format', 'json', '--fail-on', 'never', '--no-user-config'],
		{ cwd: root, encoding: 'utf8', timeout: 300_000, maxBuffer: 64 * 1024 * 1024 }
	);
	if (res.status === 2 || !res.stdout) {
		console.error(`stitcher-local: review failed in ${root} (exit ${res.status}): ${(res.stderr ?? '').slice(0, 400)}`);
		process.exit(2);
	}
	return JSON.parse(res.stdout);
}

function runMode(rootArg, change, base, ciRootArg) {
	const root = resolve(rootArg);
	let ciRoot = ciRootArg ? resolve(ciRootArg) : null;
	let worktree = null;
	if (!ciRoot) {
		// The CI side is a clean checkout of HEAD: a worktree has none of the
		// local working-tree edits or untracked files, which is exactly the
		// environment CI reviews.
		const tmp = mkdtempSync(join(tmpdir(), 'stitcher-ci-'));
		const add = spawnSync('git', ['-C', root, 'worktree', 'add', '--detach', tmp, 'HEAD'], { encoding: 'utf8' });
		if (add.status !== 0) {
			console.error(`stitcher-local: cannot create the CI worktree: ${(add.stderr ?? '').slice(0, 300)}`);
			process.exit(2);
		}
		ciRoot = tmp;
		worktree = tmp;
	}
	try {
		const local = runCli(root, change, base);
		const ci = runCli(ciRoot, change, base);
		return compareVerdicts(local, ci);
	} finally {
		if (worktree) spawnSync('git', ['-C', root, 'worktree', 'remove', '--force', worktree], { encoding: 'utf8' });
	}
}

function main(argv) {
	const opts = {};
	for (let i = 0; i < argv.length; i++) {
		const a = argv[i];
		if (!a.startsWith('--')) continue;
		const key = a.slice(2);
		const val = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : 'true';
		opts[key] = val;
	}
	let record;
	if (opts.run) {
		if (!opts.change || !opts.base) {
			console.error('stitcher-local: --run needs --change <name> and --base <ref>.');
			return 2;
		}
		record = runMode(opts.root ?? '.', opts.change, opts.base, opts['ci-root']);
	} else if (opts.local && opts.ci) {
		record = compareVerdicts(readJson(opts.local), readJson(opts.ci));
	} else {
		console.error('stitcher-local: usage: --local <json> --ci <json> | --run --change <name> --base <ref> [--root DIR] [--ci-root DIR]');
		return 2;
	}
	if (opts.out) writeFileSync(opts.out, JSON.stringify(record, null, 2) + '\n');
	console.log(JSON.stringify({ parity: record.parity, cause: record.cause, differences: record.differences }, null, 2));
	if (record.parity === 'identical') return 0;
	console.error(`stitcher-local: PARITY DEFECT - local and CI verdicts diverge (${record.differences.length} difference(s)); classify as a defect.`);
	return 1;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
	process.exit(main(process.argv.slice(2)));
}
