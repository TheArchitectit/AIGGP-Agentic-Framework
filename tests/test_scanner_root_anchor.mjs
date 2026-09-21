#!/usr/bin/env node
// Root-anchoring fixture — locks the layout contract for the three DevGate
// scanners that resolve a project root from their own file location:
// guardrails-scan.mjs, semantic-scan.mjs, and run-tests.mjs.
//
// History this test prevents from regressing (2026-09-20 external audit):
//   * run-tests.mjs and semantic-scan.mjs resolved the project root by walking
//     UP from the parent of DevGate's own directory looking for a marker file.
//     Run from inside the DevGate repo, "the parent" is a sibling-repo directory
//     like /mnt/data/git — which on this machine carries a package.json — so the
//     scanners settled there. semantic-scan then reported scanning thousands of
//     files it does not own; run-tests.mjs discovered ZERO of DevGate's own
//     tests and still printed "TOTAL: 0 passed" and exited 0. A self-test lane
//     that greener-lights on zero work is the exact silent-success failure mode
//     the whole gate exists to prevent.
//   * The correct contract already lived in guardrails-scan.mjs: the project
//     root is the directory that CONTAINS `.devgate/` (submodule layout), or
//     DevGate itself when run standalone — NEVER an ancestor chosen by a marker
//     search. All three scanners now share it via scripts/lib/project-root.mjs.
//
// The discriminating case is a STANDALONE layout whose parent DOES carry a
// marker file — the historical configuration (/mnt/data/git holds its own
// package.json): the old walk-up stopped at that marker and evaluated the
// decoys planted there; the layout contract never consults markers, so it
// stays inside the repo. A markerless parent would let an inverted-precedence
// mutant ("repo first, ancestor fallback") pass with identical assertions.
// The submodule case is a positive control (old and new agree) so a fix cannot
// over-correct to "always DevGate" and strand consumers.
//
// Run: node tests/test_scanner_root_anchor.mjs

import { spawnSync } from "node:child_process";
import { copyFileSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const scriptsDir = join(repoRoot, "scripts");

let failures = 0;
function check(name, cond, detail = "") {
	if (cond) console.log(`ok - ${name}`);
	else { failures++; console.error(`FAIL - ${name}${detail ? `: ${detail}` : ""}`); }
}

const PASSING_TEST = "import { test } from 'node:test';\ntest('t', () => {});\n";

// Install DevGate's scripts into a synthetic standalone repo
// <parent>/<repoName>/, mirroring a real checkout: the runner discovers tests
// under <root>/tests and <root>/src, so those dirs hold the in-repo truth.
function installStandalone(parent, repoName) {
	const repo = join(parent, repoName);
	mkdirSync(join(repo, "scripts", "lib"), { recursive: true });
	mkdirSync(join(repo, "tests"), { recursive: true });
	mkdirSync(join(repo, "src"), { recursive: true });
	for (const f of ["run-tests.mjs", "semantic-scan.mjs"]) {
		copyFileSync(join(scriptsDir, f), join(repo, "scripts", f));
	}
	// Post-fix the scripts import the shared contract module; pre-fix there is
	// no lib/ helper and the copy above is self-contained (the try keeps this
	// fixture runnable against the unfixed scripts, which is the point — it
	// must go RED before the fix and GREEN after).
	try {
		copyFileSync(join(scriptsDir, "lib", "project-root.mjs"),
			join(repo, "scripts", "lib", "project-root.mjs"));
	} catch { /* pre-fix */ }
	for (let i = 1; i <= 3; i++) {
		writeFileSync(join(repo, "tests", `in_repo_${i}.test.mjs`), PASSING_TEST);
	}
	// Three TS/JS source files for semantic-scan to count (it walks the whole
	// tree recursively, so placement anywhere under the repo is equivalent).
	for (let i = 1; i <= 3; i++) {
		writeFileSync(join(repo, "src", `mod_${i}.js`), "export const x = 1;\n");
	}
	return repo;
}

// Plant decoys in the PARENT, in the layout the runner's discovery reads:
// <parent>/tests/*.test.mjs + <parent>/*.js. An escaped root scans these; an
// anchored root never sees them. `markerless` keeps the parent free of
// package.json/.git — otherwise the walk-up would stop even earlier.
function plantDecoys(parent, markerless = true) {
	if (!markerless) {
		writeFileSync(join(parent, "package.json"), '{"name":"parent-decoy"}\n');
	}
	mkdirSync(join(parent, "tests"), { recursive: true });
	for (let i = 1; i <= 2; i++) {
		writeFileSync(join(parent, "tests", `decoy_${i}.test.mjs`), PASSING_TEST);
		writeFileSync(join(parent, `decoy_mod_${i}.js`), "export const d = 1;\n");
	}
}

const dirs = [];
function freshParent() {
	const d = mkdtempSync(join(tmpdir(), "dg-root-anchor-"));
	dirs.push(d);
	return d;
}

function countFiles(out) {
	const m = out.match(/across (\d+) files/);
	return m ? Number(m[1]) : null;
}

// --------------------------------------------------------------------------
// 1. run-tests.mjs — standalone repo under a MARKER-BEARING parent (the
//    historical escape condition). The old walk-up stopped at the parent's
//    package.json and evaluated the 2 decoys there; the layout contract finds
//    the repo's 3 own tests. 3-vs-2 distinguishes the trees by count, and the
//    per-file lines below name which tree ran.
// --------------------------------------------------------------------------
{
	const parent = freshParent();
	plantDecoys(parent, /* markerless */ false); // parent carries package.json
	const repo = installStandalone(parent, "gameproj");
	const res = spawnSync(process.execPath, [join(repo, "scripts", "run-tests.mjs")],
		{ encoding: "utf-8", cwd: repo });
	const out = (res.stdout ?? "") + (res.stderr ?? "");
	check("run-tests: standalone root discovers the repo's 3 tests, not the parent's 2 decoys",
		countFiles(out) === 3 && !out.includes("decoy_") && out.includes("in_repo_1"),
		`counts/out: ${JSON.stringify(out.slice(-260))}`);
	check("run-tests: standalone exits green on 3 passing files",
		res.status === 0, `exit ${res.status}`);
}

// --------------------------------------------------------------------------
// 2. run-tests.mjs — NON-VACUITY: zero discovery is an error, never a silent
//    green. An empty repo (no tests/, nothing collected) under a decoy parent
//    must fail with the reason, never fall back to the parent. This kills the
//    general "TOTAL: 0 passed => exit 0" shape the audit flagged AND the
//    inverted-precedence mutant (repo first, ancestor fallback): the fallback
//    would find the parent's 2 decoys and exit 0.
// --------------------------------------------------------------------------
{
	const parent = freshParent();
	plantDecoys(parent, /* markerless */ false); // parent carries package.json
	const repo = join(parent, "emptyproj");
	mkdirSync(join(repo, "scripts", "lib"), { recursive: true });
	copyFileSync(join(scriptsDir, "run-tests.mjs"), join(repo, "scripts", "run-tests.mjs"));
	try {
		copyFileSync(join(scriptsDir, "lib", "project-root.mjs"),
			join(repo, "scripts", "lib", "project-root.mjs"));
	} catch { /* pre-fix */ }
	const res = spawnSync(process.execPath, [join(repo, "scripts", "run-tests.mjs")],
		{ encoding: "utf-8", cwd: repo });
	const out = (res.stdout ?? "") + (res.stderr ?? "");
	check("run-tests: zero discovery fails closed with a reason, never exits 0",
		res.status !== 0 && /no test files discovered/.test(out),
		`exit ${res.status}: ${JSON.stringify(out.slice(-200))}`);
	// The escape path would instead have found the parent's 2 decoys.
	check("run-tests: empty repo did not scan the parent",
		countFiles(out) !== 2, "count 2 = scanned the decoy parent");
}

// --------------------------------------------------------------------------
// 3. semantic-scan.mjs — standalone under a marker-bearing parent. With
//    DEVGATE_SEMANTIC_REQUIRED=0 the script prints the count of files it
//    COUNTED (and says it evaluated none) and exits 0; the count is the anchor
//    assertion. Correct = 3 (repo src) + 0 decoys; escaped = 3 + 2 decoy_mod
//    at the parent = 5.
// --------------------------------------------------------------------------
{
	const parent = freshParent();
	plantDecoys(parent, /* markerless */ false); // parent carries package.json
	const repo = installStandalone(parent, "gameproj");
	const res = spawnSync(process.execPath, [join(repo, "scripts", "semantic-scan.mjs")],
		{ encoding: "utf-8", cwd: repo,
			env: { ...process.env, DEVGATE_SEMANTIC_REQUIRED: "0" } });
	const out = (res.stdout ?? "") + (res.stderr ?? "");
	const m = out.match(/counted (\d+) TS\/JS file\(s\)/);
	check("semantic-scan: standalone counts only the repo's own files, not the parent's decoys",
		m && Number(m[1]) === 3,
		`expected 3 counted, got: ${m ? m[1] : "no match"} :: ${JSON.stringify(out.slice(-200))}`);
}

// --------------------------------------------------------------------------
// 4. Submodule layout positive control. DevGate at <proj>/.devgate/, <proj>
//    has a marker. Root must be <proj>, so the consumer's tests are found.
//    Old walk-up and layout contract agree here — this guards against a fix
//    that over-corrects ("root is always the script's own tree") and strands
//    real consumers.
// --------------------------------------------------------------------------
{
	const parent = freshParent();
	const proj = join(parent, "consumer");
	mkdirSync(join(proj, ".devgate", "scripts", "lib"), { recursive: true });
	mkdirSync(join(proj, "tests"), { recursive: true });
	writeFileSync(join(proj, "package.json"), '{"name":"consumer"}\n');
	copyFileSync(join(scriptsDir, "run-tests.mjs"),
		join(proj, ".devgate", "scripts", "run-tests.mjs"));
	try {
		copyFileSync(join(scriptsDir, "lib", "project-root.mjs"),
			join(proj, ".devgate", "scripts", "lib", "project-root.mjs"));
	} catch { /* pre-fix */ }
	for (let i = 1; i <= 2; i++) {
		writeFileSync(join(proj, "tests", `app_${i}.test.mjs`), PASSING_TEST);
	}
	// And a decoy inside .devgate/tests: skipped by SKIP_DIRS either way —
	// the consumer's own tree is the scan, DevGate's copy is not.
	mkdirSync(join(proj, ".devgate", "tests"), { recursive: true });
	writeFileSync(join(proj, ".devgate", "tests", "vendored.test.mjs"), PASSING_TEST);
	const res = spawnSync(process.execPath,
		[join(proj, ".devgate", "scripts", "run-tests.mjs")],
		{ encoding: "utf-8", cwd: proj });
	const out = (res.stdout ?? "") + (res.stderr ?? "");
	check("run-tests: submodule layout discovers the CONSUMER's tests only",
		countFiles(out) === 2 && out.includes("app_1") && !out.includes("vendored"),
		`out: ${JSON.stringify(out.slice(-260))}`);
	check("run-tests: consumer layout run exits green",
		res.status === 0, `exit ${res.status}`);
}

// --------------------------------------------------------------------------
// 5. The honest-skip escape hatch. DEVGATE_ALLOW_NO_TESTS=1 turns zero
//    discovery into a loud, explicit skip (exit 0 with a "skip, not a pass"
//    line) — and ONLY the literal "1" does: a truthy-string mutant would let
//    "0" silently skip real test-less-looking roots.
// --------------------------------------------------------------------------
{
	const parent = freshParent();
	plantDecoys(parent, /* markerless */ false); // parent carries package.json
	const repo = join(parent, "emptyproj");
	mkdirSync(join(repo, "scripts", "lib"), { recursive: true });
	copyFileSync(join(scriptsDir, "run-tests.mjs"), join(repo, "scripts", "run-tests.mjs"));
	copyFileSync(join(scriptsDir, "lib", "project-root.mjs"),
		join(repo, "scripts", "lib", "project-root.mjs"));
	const skip = spawnSync(process.execPath, [join(repo, "scripts", "run-tests.mjs")],
		{ encoding: "utf-8", cwd: repo, env: { ...process.env, DEVGATE_ALLOW_NO_TESTS: "1" } });
	const skipOut = (skip.stdout ?? "") + (skip.stderr ?? "");
	check("run-tests: ALLOW_NO_TESTS=1 skips loudly and exits 0",
		skip.status === 0 && /SKIPPED via DEVGATE_ALLOW_NO_TESTS=1/.test(skipOut) &&
		/this is a skip, not a pass/.test(skipOut),
		`exit ${skip.status}: ${JSON.stringify(skipOut.slice(-200))}`);
	const zero = spawnSync(process.execPath, [join(repo, "scripts", "run-tests.mjs")],
		{ encoding: "utf-8", cwd: repo, env: { ...process.env, DEVGATE_ALLOW_NO_TESTS: "0" } });
	check("run-tests: ALLOW_NO_TESTS=0 does NOT skip (only literal 1 is the hatch)",
		zero.status !== 0 && /no test files discovered/.test((zero.stderr ?? "") + (zero.stdout ?? "")),
		`exit ${zero.status}`);
}

for (const d of dirs) rmSync(d, { recursive: true, force: true });

if (failures) {
	console.error(`\n${failures} root-anchor check(s) failed`);
	process.exit(1);
}
console.log("\nall root-anchor checks passed");
