// // spec: fw-test-01, gate-vacuous-01
// Runner-selection contract for scripts/run-tests.mjs (lib/test-runner-select.mjs).
//
// Two measured defects pinned here:
//
//   1. node --test cannot execute a vitest suite — every file in a vitest
//      consumer crashed with ERR_MODULE_NOT_FOUND on its extensionless TS
//      imports (measured 2026-10-27 on vbrainstorm src/community/media.test.ts).
//      A consumer whose package.json declares vitest must have its suffix-style
//      JS/TS files delegated to the local vitest binary (relative filter, TAP
//      reporter), and nothing else may change engines (prefix-style test_*.mjs
//      stays on node --test — vitest's default include does not collect it).
//
//   2. A run that executed ZERO tests must not look green: node --test on an
//      empty file and vitest with a non-matching filter both print a 1..0 plan
//      and exit 0 (gate-vacuous-01). isEmptyRun() names that state; run-tests
//      fails it closed both in the verdict and in solo flake adjudication.
//
//   3. A nested `node --test` skips every file: the outer runner marks its
//      children with NODE_TEST_CONTEXT, and a child that inherits it treats
//      its own `node --test` as recursive ("skipping running files", measured
//      v26.11.1). run-tests.mjs must scrub that marker (childTestEnv) or every
//      engine it spawns evaluates nothing while the fixture looks broken.
//
// The spawn-level test drives the REAL scripts/run-tests.mjs against a fixture
// consumer with a STUB vitest binary — so selection, spawning, TAP parsing and
// the verdict are exercised as one behavior, not as a mock of any of them.

import { test } from "node:test";
import assert from "node:assert/strict";
import { chmodSync, copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { spawnSync } from "node:child_process";

import { childTestEnv, declaresVitest, isEmptyRun, isSuffixTestFile, selectJsRunner }
	from "../scripts/lib/test-runner-select.mjs";

const SCRIPTS = join(import.meta.dirname, "..", "scripts");

test("isSuffixTestFile: vitest-collected names only", () => {
	assert.equal(isSuffixTestFile("src/community/media.test.ts"), true);
	assert.equal(isSuffixTestFile("src/App.spec.tsx"), true);
	assert.equal(isSuffixTestFile("tests/test_guardrails_scan.mjs"), false);
	assert.equal(isSuffixTestFile("tests/test_python_root_anchor.py"), false);
	assert.equal(isSuffixTestFile("src/not_a_test.ts"), false);
});

test("selectJsRunner: declared vitest delegates suffix-style files", () => {
	// Production hands absolute paths (walk output, solo re-run join).
	const picked = selectJsRunner(join("/proj", "src", "community", "media.test.ts"), {
		projectRoot: "/proj", vitestDeclared: true, timeoutMs: 5000,
	});
	assert.equal(picked.args[0], "run");
	assert.ok(picked.args.includes("--reporter=tap"), picked.args.join(" "));
	assert.ok(picked.args.includes("--root"), "root must be pinned");
	// The filter MUST be relative: vitest matches filters against relative
	// test paths, so an absolute path matches nothing (1..0 trap).
	assert.equal(picked.args.at(-1), join("src", "community", "media.test.ts"));
});

test("selectJsRunner: declared vitest keeps prefix-style on node --test", () => {
	const picked = selectJsRunner("tests/test_guardrails_scan.mjs", {
		projectRoot: "/proj", vitestDeclared: true, timeoutMs: 5000, execPath: "/bin/node",
	});
	assert.equal(picked.cmd, "/bin/node");
	assert.equal(picked.args[0], "--test");
});

test("selectJsRunner: no vitest keeps every JS/TS file on node --test", () => {
	const picked = selectJsRunner("src/community/media.test.ts", {
		projectRoot: "/proj", vitestDeclared: false, timeoutMs: 5000, execPath: "/bin/node",
	});
	assert.equal(picked.cmd, "/bin/node");
	assert.equal(picked.args[0], "--test");
});

test("declaresVitest: reads the consumer's package.json, fails closed to false", () => {
	const dir = mkdtempSync(join(tmpdir(), "dg-vitest-decl-"));
	try {
		assert.equal(declaresVitest(dir), false); // no package.json
		writeFileSync(join(dir, "package.json"),
			JSON.stringify({ name: "c", devDependencies: { vitest: "^5.0.5" } }));
		assert.equal(declaresVitest(dir), true);
		writeFileSync(join(dir, "package.json"),
			JSON.stringify({ name: "c", dependencies: { vitest: "^5.0.5" } }));
		assert.equal(declaresVitest(dir), true);
		writeFileSync(join(dir, "package.json"),
			JSON.stringify({ name: "c", devDependencies: { vite: "^6" } }));
		assert.equal(declaresVitest(dir), false);
	} finally {
		rmSync(dir, { recursive: true, force: true });
	}
});

test("isEmptyRun: the 1..0 plan is vacuous; skips count as evidence", () => {
	assert.equal(isEmptyRun({ pass: 0, fail: 0, okCount: 0, notOkCount: 0, skipped: 0 }), true);
	assert.equal(isEmptyRun({ pass: 0, fail: 0, okCount: 1, notOkCount: 0, skipped: 0 }), false);
	assert.equal(isEmptyRun({ pass: 3, fail: 0, okCount: 0, notOkCount: 0, skipped: 0 }), false);
	assert.equal(isEmptyRun({ pass: 0, fail: 0, okCount: 0, notOkCount: 0, skipped: 2 }), false);
	assert.equal(isEmptyRun({ pass: 0, fail: 1, okCount: 0, notOkCount: 1, skipped: 0 }), false);
});

test("childTestEnv: scrubs NODE_TEST_CONTEXT, keeps the rest", () => {
	const env = childTestEnv({ PATH: "/bin", NODE_TEST_CONTEXT: "child-v8", KEEP: "1" }, "/tmp/iso");
	assert.equal(env.NODE_TEST_CONTEXT, undefined);
	assert.equal(env.PATH, "/bin");
	assert.equal(env.KEEP, "1");
	assert.equal(env.TMPDIR, "/tmp/iso");
});

// --- spawn-level: the REAL run-tests.mjs against a stub-vitest consumer -------
//
// The runner's project root comes from its OWN file location (the layout
// contract — never cwd), so the fixture must carry its own copy of the
// scripts/, exactly like test_scanner_root_anchor.mjs stages them. Running
// the checkout's run-tests.mjs would resolve the checkout's root and
// discover the checkout's tests instead of the fixture's.

function fixtureConsumer({ stubPlan, stubExit }) {
	const root = mkdtempSync(join(tmpdir(), "dg-run-tests-vt-"));
	const scripts = join(root, "scripts");
	mkdirSync(join(scripts, "lib"), { recursive: true });
	copyFileSync(join(SCRIPTS, "run-tests.mjs"), join(scripts, "run-tests.mjs"));
	for (const f of ["gate_common.mjs", "project-root.mjs", "test-runner-select.mjs"]) {
		copyFileSync(join(SCRIPTS, "lib", f), join(scripts, "lib", f));
	}
	// loadSkipDirs fails closed without the scope contract — same fixture
	// requirement as test_python_root_anchor.py documents for regression_sizes.
	mkdirSync(join(root, ".guardrails"), { recursive: true });
	copyFileSync(join(SCRIPTS, "..", ".guardrails", "scope.json"),
		join(root, ".guardrails", "scope.json"));
	writeFileSync(join(root, "package.json"),
		JSON.stringify({ name: "vt-consumer", devDependencies: { vitest: "^5.0.5" } }));
	mkdirSync(join(root, "src"));
	writeFileSync(join(root, "src", "thing.test.ts"),
		"// executed by the stub, not by node --test\n");
	const bin = join(root, "node_modules", ".bin");
	mkdirSync(bin, { recursive: true });
	// Stub vitest: records argv, emits the TAP plan it was told to, exits.
	const stub = join(bin, "vitest");
	writeFileSync(stub, `#!/bin/sh
echo "$@" > "$STUB_ARGV_LOG"
printf 'TAP version 13\\n'
printf '${stubPlan}\\n'
exit ${stubExit}
`);
	chmodSync(stub, 0o755);
	return root;
}

function runRealRunner(root, extraEnv = {}) {
	const argvLog = join(root, "argv.log");
	const res = spawnSync(process.execPath, [join(root, "scripts", "run-tests.mjs")], {
		cwd: root,
		encoding: "utf8",
		env: { ...process.env, STUB_ARGV_LOG: argvLog, DEVGATE_TEST_POOL: "1", ...extraEnv },
		timeout: 60_000,
	});
	const out = (res.stdout || "") + (res.stderr || "");
	let argv = "";
	try {
		argv = readFileSync(argvLog, "utf8").trim();
	} catch { /* stub never ran */ }
	return { status: res.status, out, argv };
}

test("run-tests delegates to the stub vitest and reads its TAP as a pass", () => {
	const root = fixtureConsumer({ stubPlan: "1..1\\nok 1 - src/thing.test.ts", stubExit: 0 });
	try {
		const { status, out, argv } = runRealRunner(root);
		assert.match(argv, /^run --reporter=tap --root /, `vitest argv: ${argv}`);
		assert.match(argv, /src\/thing\.test\.ts$/, `vitest filter: ${argv}`);
		assert.equal(status, 0, out);
		assert.match(out, /1 pass \/ 0 fail/);
		assert.doesNotMatch(out, /ran zero tests/, out);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test("run-tests fails a 1..0 stub run closed (vacuous green refused)", () => {
	const root = fixtureConsumer({ stubPlan: "1..0", stubExit: 0 });
	try {
		const { status, out } = runRealRunner(root);
		assert.notEqual(status, 0, out);
		assert.match(out, /ran zero tests — vacuous, not a pass/, out);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

// --- nested execution: the runner under `node --test` ------------------------
//
// run-tests.mjs is itself executed under `node --test` by its own fixture
// suite (and by consumers' CI lanes). A `node --test` runner marks its test
// files with NODE_TEST_CONTEXT; if run-tests forwards that marker to ITS
// children, a nested `node --test` treats the invocation as recursive and
// SKIPS RUNNING FILES ("run() is being called recursively within a test file.
// skipping running files.", measured v26.11.1) — zero tests, exit 0. The
// vacuous guard correctly fails that closed; the fix is that the runner must
// never contaminate its children (childTestEnv). This test reproduces the
// contaminated ambient exactly.

function fixtureNodeConsumer() {
	const root = mkdtempSync(join(tmpdir(), "dg-run-tests-node-"));
	const scripts = join(root, "scripts");
	mkdirSync(join(scripts, "lib"), { recursive: true });
	copyFileSync(join(SCRIPTS, "run-tests.mjs"), join(scripts, "run-tests.mjs"));
	for (const f of ["gate_common.mjs", "project-root.mjs", "test-runner-select.mjs"]) {
		copyFileSync(join(SCRIPTS, "lib", f), join(scripts, "lib", f));
	}
	mkdirSync(join(root, ".guardrails"), { recursive: true });
	copyFileSync(join(SCRIPTS, "..", ".guardrails", "scope.json"),
		join(root, ".guardrails", "scope.json"));
	mkdirSync(join(root, "tests"));
	writeFileSync(join(root, "tests", "plain.test.mjs"),
		"import { test } from 'node:test';\ntest('t', () => {});\n");
	return root;
}

test("run-tests children run top-level even when the runner sits under node --test", () => {
	const root = fixtureNodeConsumer();
	try {
		const { status, out } = runRealRunner(root, { NODE_TEST_CONTEXT: "child-v8" });
		assert.equal(status, 0, out);
		assert.match(out, /1 pass \/ 0 fail/);
		assert.doesNotMatch(out, /ran zero tests/, out);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});
