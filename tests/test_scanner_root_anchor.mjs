// Fixture tests for scanner ROOT ANCHORING (audit findings C2/C3).
//
// History these tests prevent from regressing:
//   * semantic-scan.mjs and run-tests.mjs both used a findProjectRoot() that
//     walked UP from .devgate's parent and returned the walk's START
//     directory when no marker was found. On a standalone DevGate clone that
//     start is the repo's PARENT: semantic-scan crashed on a sibling's EACCES
//     (or scanned stranger trees), and run-tests reported "0 passed, 0 failed
//     across 0 files" exit 0 while the repo's own tests sat unrun — the
//     flagship silent-success failure mode, inside the tools that exist to
//     prevent it. guardrails-scan.mjs fixed this with the `.devgate` basename
//     layout contract; the fix was never ported. These tests lock the port.
//
// Run: node tests/test_scanner_root_anchor.mjs
import { spawnSync } from "node:child_process";
import { chmodSync, copyFileSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const semanticScan = join(repoRoot, "scripts", "semantic-scan.mjs");
const runTests = join(repoRoot, "scripts", "run-tests.mjs");

let failures = 0;
function check(name, cond, detail = "") {
	if (cond) console.log(`ok - ${name}`);
	else { failures++; console.error(`FAIL - ${name}${detail ? `: ${detail}` : ""}`); }
}

// Layout: <base>/sibling/  (a broken tree that must NEVER be scanned)
//         <base>/proj/     (standalone DevGate-shaped project)
function makeStandalone() {
	const base = mkdtempSync(join(tmpdir(), "dg-anchor-"));
	const proj = join(base, "proj");
	mkdirSync(join(proj, "scripts"), { recursive: true });
	mkdirSync(join(proj, "tests"), { recursive: true });
	mkdirSync(join(base, "sibling"), { recursive: true });
	copyFileSync(semanticScan, join(proj, "scripts", "semantic-scan.mjs"));
	copyFileSync(runTests, join(proj, "scripts", "run-tests.mjs"));
	// A file the scanner MUST find (so file-count proves scope).
	writeFileSync(join(proj, "app.js"), "doThing().then((x) => x);\n");
	// A sibling violation that must NOT be scanned.
	writeFileSync(join(base, "sibling", "evil.js"), "evil().then((x) => x);\n");
	// A sibling directory that would EACCES-crash the old walk-up (no-op when
	// tests run as root, where mode bits do not restrict access).
	const locked = join(base, "sibling", "locked");
	mkdirSync(locked, { recursive: true });
	try { chmodSync(locked, 0o000); } catch { /* ignored */ }
	// One passing pytest file in the project's tests/ tree.
	writeFileSync(join(proj, "tests", "test_sample.py"),
		"def test_ok():\n    assert True\n");
	return { base, proj };
}

// --- 1. semantic-scan anchors to the standalone repo, not its parent --------
{
	const { base, proj } = makeStandalone();
	const r = spawnSync(process.execPath, [join(proj, "scripts", "semantic-scan.mjs")], {
		cwd: base, encoding: "utf-8",
		env: { ...process.env, DEVGATE_SEMANTIC_REQUIRED: "0" },
	});
	// Without typescript the gate exits 0 with an explicit SKIPPED line that
	// names the file count — the count proves WHICH tree was walked.
	const out = r.stdout + r.stderr;
	check("semantic-scan: exit 0 with explicit SKIPPED (no parser)", r.status === 0, out);
	check("semantic-scan: found exactly the project's own 1 TS/JS file",
		/1 TS\/JS file/.test(out), out);
	check("semantic-scan: did not scan the sibling tree",
		!/evil\.js/.test(out), out);
	rmSync(base, { recursive: true, force: true });
}

// --- 2. run-tests discovers the repo's own tests (non-zero), not zero -------
{
	const { base, proj } = makeStandalone();
	const r = spawnSync(process.execPath, [join(proj, "scripts", "run-tests.mjs")], {
		cwd: base, encoding: "utf-8",
		env: { ...process.env, DEVGATE_TEST_TIMEOUT: "30000" },
	});
	const out = (r.stdout || "") + (r.stderr || "");
	check("run-tests: finds test files in a standalone clone",
		/across 1 files/.test(out), out);
	check("run-tests: exit 0", r.status === 0, out);
	check("run-tests: did not run sibling tests", !/evil/.test(out), out);
	rmSync(base, { recursive: true, force: true });
}

console.log(failures === 0 ? "\nALL TESTS PASSED" : `\n${failures} TEST(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
