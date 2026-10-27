// // spec: fw-test-01, gate-vacuous-01
// Runner selection for scripts/run-tests.mjs — which engine executes a
// discovered JS/TS test file, and when a finished run evaluated nothing.
//
// Split out of run-tests.mjs (2026-10-27) so the selection contract is unit
// testable without spawning the whole runner. Two measured defects live here:
//
//   1. `node --test` cannot execute a vitest suite. It loads the .ts file but
//      its resolver does not do TypeScript module resolution, so the file's
//      extensionless relative imports die with ERR_MODULE_NOT_FOUND (measured
//      on vbrainstorm src/community/media.test.ts: "Cannot find module
//      '.../src/community/media'"). Every file in a vitest consumer crashed
//      before a single test ran — the TS discovery arm existed but could not
//      actually run the dominant TS layout. When the consumer's package.json
//      DECLARES vitest, suffix-style JS/TS files are delegated to the local
//      vitest binary (TAP reporter, project root pinned, relative filter).
//
//   2. A run that executed ZERO tests must not look green. `node --test` on a
//      file with no tests prints "TAP version 13 / 1..0" and exits 0; vitest
//      with a filter that matches nothing prints the same plan. Either reads
//      as ✓ 0 pass / 0 fail under a naive verdict — the gate-vacuous-01 shape
//      this framework exists to refuse. isEmptyRun() names that state so
//      run-tests.mjs fails it closed.
//
// Named limit: only suffix-style names (*.test.* / *.spec.*) are delegated to
// vitest, because that is what vitest's default include collects. Prefix-style
// (test_*.mjs) stays on `node --test` — it is the node:test convention, and
// vitest's collection would not pick it up (a delegated prefix file would hit
// the 1..0 trap and fail closed, which is honest but wrong).

import { basename, join, relative } from "node:path";
import { existsSync, readFileSync } from "node:fs";

/** True when the consumer's package.json declares vitest as a direct dep. */
export function declaresVitest(projectRoot) {
	try {
		const pkg = JSON.parse(readFileSync(join(projectRoot, "package.json"), "utf8"));
		return Boolean(pkg?.dependencies?.vitest || pkg?.devDependencies?.vitest);
	} catch {
		return false; // no package.json, or unreadable: node --test stays the engine
	}
}

/** Suffix-style test names (*.test.* / *.spec.*) — vitest's default include. */
export function isSuffixTestFile(filename) {
	return /\.(test|spec)\.(?:[cm]?[jt]sx?)$/.test(basename(filename).toLowerCase());
}

/**
 * Pick the engine and argv for one JS/TS test file.
 *
 * Returns { cmd, args } ready for spawn with cwd=projectRoot. The vitest
 * filter is the file's path RELATIVE to projectRoot: vitest filters match
 * against relative test paths, so an absolute path matches nothing and the
 * run would hit the 1..0 trap.
 */
export function selectJsRunner(file, { projectRoot, vitestDeclared, timeoutMs = 120_000, execPath = process.execPath }) {
	if (vitestDeclared && isSuffixTestFile(file)) {
		const localBin = join(projectRoot, "node_modules", ".bin", "vitest");
		// Missing local binary fails loud at spawn (ENOENT → crashed marker);
		// declaring vitest in package.json without installing it is a broken
		// consumer, not a reason to silently fall back to an engine that
		// cannot run the file.
		return {
			cmd: existsSync(localBin) ? localBin : "vitest",
			args: ["run", "--reporter=tap", "--root", projectRoot,
				relative(projectRoot, file)],
		};
	}
	return {
		cmd: execPath,
		args: ["--test", "--test-concurrency=1", "--test-reporter=tap",
			"--test-force-exit", `--test-timeout=${timeoutMs}`, file],
	};
}

/**
 * Environment for a spawned test engine: a CLEAN top-level run, never a
 * nested one. `node --test` marks its own children with NODE_TEST_CONTEXT;
 * a child that inherits it treats its `node --test` invocation as recursive
 * and SKIPS RUNNING FILES entirely (measured 2026-10-27 on v26.11.1: "run()
 * is being called recursively within a test file. skipping running files.") —
 * zero tests, exit 0, the gate-vacuous-01 shape. run-tests.mjs can itself be
 * executed under `node --test` (its own fixture suite is), so the runner must
 * scrub the marker before spawning any engine — node, vitest, pytest or cargo.
 */
export function childTestEnv(baseEnv, tmpdir) {
	const env = { ...baseEnv, TMPDIR: tmpdir };
	delete env.NODE_TEST_CONTEXT;
	return env;
}

/**
 * The gate-vacuous-01 shape for one finished run: zero test evidence at all.
 * `skipped` counts as evidence — an honest skip ran a collection — while a
 * 1..0 plan, a crashed import and an empty filter all leave every counter 0.
 * Named limit: node:test `todo`-only files are not counted as evidence (the
 * runner does not parse `# todo`); such a file fails closed, which is the
 * conservative direction.
 */
export function isEmptyRun(r) {
	return (r.pass ?? 0) === 0 && (r.fail ?? 0) === 0 &&
		(r.okCount ?? 0) === 0 && (r.notOkCount ?? 0) === 0 &&
		(r.skipped ?? 0) === 0;
}
