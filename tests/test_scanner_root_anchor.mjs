#!/usr/bin/env node
// // spec: root-anchor-01, root-anchor-02, root-anchor-03
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
// stays inside the repo. The parent marker matters: without it an
// inverted-precedence mutant ("repo first, ancestor fallback") would pass with
// identical assertions, so every decoy parent carries one.
// The submodule case is a positive control (old and new agree) so a fix cannot
// over-correct to "always DevGate" and strand consumers. Case 8 covers the
// converse: a mis-cased `.DevGate` is NOT the marker.
//
// Run: node tests/test_scanner_root_anchor.mjs

import { spawnSync } from "node:child_process";
import { copyFileSync, cpSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
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
	for (const f of ["run-tests.mjs", "semantic-scan.mjs", "guardrails-scan.mjs"]) {
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
	// Four source files for semantic-scan to count (it walks the whole tree
	// recursively, so placement anywhere under the repo is equivalent). Three
	// .js plus one .mjs: DevGate's own first-party modules are .mjs, and this
	// repo has zero .js/.ts — a walk that matches only the old extensions
	// reports "no files, skipped" over an entire ESM codebase. The semantic
	// count assertions expect 11 = these 4 + the 4 copied scripts/*.mjs +
	// the 3 tests/in_repo_*.test.mjs (the walk excludes only .test.ts/.spec.ts,
	// not .mjs tests), so any extension drift in the walk shows immediately.
	for (const f of ["mod_1.js", "mod_2.js", "mod_3.js", "mod_4.mjs"]) {
		writeFileSync(join(repo, "src", f), "export const x = 1;\n");
	}
	// guardrails-scan.mjs loads its bundled rules from <devgateRoot>/.guardrails/.
	// Without them the scanner has zero rules, finds nothing, and reports a
	// clean scan — which would make the guardrails case below pass vacuously
	// against any root at all.
	cpSync(join(repoRoot, ".guardrails"), join(repo, ".guardrails"), { recursive: true });
	return repo;
}

// Plant decoys in the PARENT, in the layout the runner's discovery reads:
// <parent>/tests/*.test.mjs + <parent>/*.js. An escaped root scans these; an
// anchored root never sees them. The parent ALWAYS carries package.json — that
// is the historical escape precondition (the real parent, /mnt/data/git, has
// one), and it is what makes the ancestor-walk mutants killable at all. An
// earlier version of this fixture left the marker optional; every caller now
// wants it, so the parameter is gone rather than defaulted to an unused value.
function plantDecoys(parent) {
	writeFileSync(join(parent, "package.json"), '{"name":"parent-decoy"}\n');
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
	plantDecoys(parent); // parent carries package.json
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
	plantDecoys(parent); // parent carries package.json
	const repo = join(parent, "emptyproj");
	mkdirSync(join(repo, "scripts", "lib"), { recursive: true });
	copyFileSync(join(scriptsDir, "run-tests.mjs"), join(repo, "scripts", "run-tests.mjs"));
	try {
		copyFileSync(join(scriptsDir, "lib", "project-root.mjs"),
			join(repo, "scripts", "lib", "project-root.mjs"));
	} catch { /* pre-fix */ }
	// fw-scope-01: the runner refuses to run without its scope contract, so
	// plant one (root layout, like installStandalone's cpSync) — the check is
	// about zero-discovery behavior, not about a missing contract.
	cpSync(join(repoRoot, ".guardrails"), join(repo, ".guardrails"), { recursive: true });
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
	plantDecoys(parent); // parent carries package.json
	const repo = installStandalone(parent, "gameproj");
	const res = spawnSync(process.execPath, [join(repo, "scripts", "semantic-scan.mjs")],
		{ encoding: "utf-8", cwd: repo,
			env: { ...process.env, DEVGATE_SEMANTIC_REQUIRED: "0" } });
	const out = (res.stdout ?? "") + (res.stderr ?? "");
	const m = out.match(/counted (\d+) TS\/JS file\(s\)/);
	check("semantic-scan: standalone counts only the repo's own files, not the parent's decoys",
		m && Number(m[1]) === 11,
		`expected 11 counted, got: ${m ? m[1] : "no match"} :: ${JSON.stringify(out.slice(-200))}`);
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
	// A real submodule install carries DevGate's .guardrails INSIDE .devgate —
	// that is where the scope-contract lookup (root-first, devgateRoot-second)
	// finds it for a consumer.
	cpSync(join(repoRoot, ".guardrails"), join(proj, ".devgate", ".guardrails"), { recursive: true });
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
	plantDecoys(parent); // parent carries package.json
	const repo = join(parent, "emptyproj");
	mkdirSync(join(repo, "scripts", "lib"), { recursive: true });
	copyFileSync(join(scriptsDir, "run-tests.mjs"), join(repo, "scripts", "run-tests.mjs"));
	copyFileSync(join(scriptsDir, "lib", "project-root.mjs"),
		join(repo, "scripts", "lib", "project-root.mjs"));
	// fw-scope-01: plant the scope contract so the runner gets past its
	// contract check and the assertions below see the skip behavior.
	cpSync(join(repoRoot, ".guardrails"), join(repo, ".guardrails"), { recursive: true });
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

// --------------------------------------------------------------------------
// 6. cwd independence. The root is resolved from the SCRIPT'S OWN location
//    (import.meta.url), so invoking a scanner from an unrelated working
//    directory must not change which tree it evaluates. Without this case a
//    `return process.cwd()` mutant passes every check above — every other case
//    spawns with cwd inside the tree under test, where cwd and layout agree.
//    The foreign cwd deliberately carries its OWN tests and its own package.json
//    so a cwd-rooted scanner finds a populated, green, wrong tree rather than
//    failing for a reason the assertion could confuse with correctness.
// --------------------------------------------------------------------------
{
	const foreign = freshParent();
	plantDecoys(foreign);
	const parent = freshParent();
	const repo = installStandalone(parent, "gameproj");

	const res = spawnSync(process.execPath, [join(repo, "scripts", "run-tests.mjs")],
		{ encoding: "utf-8", cwd: foreign });
	const out = (res.stdout ?? "") + (res.stderr ?? "");
	check("run-tests: resolves its own tree when invoked from an unrelated cwd",
		countFiles(out) === 3 && out.includes("in_repo_1") && !out.includes("decoy_"),
		`counts/out: ${JSON.stringify(out.slice(-260))}`);

	const sem = spawnSync(process.execPath, [join(repo, "scripts", "semantic-scan.mjs")],
		{ encoding: "utf-8", cwd: foreign,
			env: { ...process.env, DEVGATE_SEMANTIC_REQUIRED: "0" } });
	const semOut = (sem.stdout ?? "") + (sem.stderr ?? "");
	const sm = semOut.match(/counted (\d+) TS\/JS file\(s\)/);
	check("semantic-scan: resolves its own tree when invoked from an unrelated cwd",
		sm && Number(sm[1]) === 11,
		`expected 11 counted, got: ${sm ? sm[1] : "no match"} :: ${JSON.stringify(semOut.slice(-200))}`);
}

// --------------------------------------------------------------------------
// 7. guardrails-scan.mjs shares the same contract. The fixture header claims to
//    lock all three scanners; without this case nothing executes the third one.
//    Asserted through its real output: the guardrails scan names the project
//    root it selected and the number of files it evaluated, so a walk-up that
//    settled on the decoy parent is visible as the wrong root, not just a
//    different count.
// --------------------------------------------------------------------------
{
	const parent = freshParent();
	plantDecoys(parent);
	const repo = installStandalone(parent, "gameproj");
	// Plant an identical rule-tripping file on BOTH sides. The rule is
	// PREVENT-001 ("JSON.parse(...) direct property access", severity error,
	// scoped to *.js/*.ts) — chosen because it is language-scoped to plain JS
	// (Godot/Rust-shaped rules like PREVENT-004 never fire on a .js file) and
	// has no forbidden_context that could suppress this shape. The reported
	// violation path then names the tree actually scanned: a walk-up that
	// settled on the decoy parent reports the parent's copy. Asserted through
	// real output rather than a debug flag, so it holds for any scanner that
	// reports the paths it evaluated.
	const trip = "export const cfg = JSON.parse(raw).timeout;\n";
	writeFileSync(join(repo, "src", "trip.js"), trip);
	writeFileSync(join(parent, "decoy_trip.js"), trip);

	const res = spawnSync(process.execPath, [join(repo, "scripts", "guardrails-scan.mjs")],
		{ encoding: "utf-8", cwd: repo });
	const out = (res.stdout ?? "") + (res.stderr ?? "");
	check("guardrails-scan: reports the repo's own file, never the decoy parent's",
		out.includes("trip.js") && !out.includes("decoy_trip"),
		`out: ${JSON.stringify(out.slice(-300))}`);
}

// --------------------------------------------------------------------------
// 7b. The guardrails SCOPE CONTRACT is cwd-independent too. fw-scope-01 made
//     skip_dirs a data file (.guardrails/scope.json) and the shipped lookup
//     walked up from process.cwd() — re-entering the root-anchor-01 escape
//     class through DATA: run from any directory above the repo, it reads a
//     FOREIGN scope.json whose skip_dirs silently reshape what the gate
//     evaluates (here: the trip file's own directory, for a clean scan of a
//     tree that was never actually scanned). Case 6 kills the same mutant in
//     run-tests/semantic-scan — their foreign cwd carries no contract at all,
//     so a walk-up throws; guardrails-scan needs a foreign scope whose
//     suppression IS observable. Case 7's spawn (cwd == repo) cannot see this:
//     there, cwd and layout agree and the walk-up reads the right file.
// --------------------------------------------------------------------------
{
	const parent = freshParent();
	plantDecoys(parent);
	const repo = installStandalone(parent, "gameproj");
	const trip = "export const cfg = JSON.parse(raw).timeout;\n";
	writeFileSync(join(repo, "src", "trip.js"), trip);
	// Foreign contract at the invocation cwd's own level: skips the very
	// directory the trip file lives in. A layout-root lookup never sees it.
	mkdirSync(join(parent, ".guardrails"), { recursive: true });
	writeFileSync(join(parent, ".guardrails", "scope.json"),
		JSON.stringify({ skip_dirs: ["src", "tests", "node_modules"] }) + "\n");
	const res = spawnSync(process.execPath, [join(repo, "scripts", "guardrails-scan.mjs")],
		{ encoding: "utf-8", cwd: parent });
	const out = (res.stdout ?? "") + (res.stderr ?? "");
	check("guardrails-scan: scope contract resolves from the layout root, not a cwd walk-up",
		out.includes("trip.js") && !out.includes("decoy_trip"),
		`exit ${res.status} out: ${JSON.stringify(out.slice(-300))}`);
}

// --------------------------------------------------------------------------
// 8. The contract name is case-exact. A directory named `.DevGate` (or any
//    other casing) is NOT the submodule marker, so a scanner installed there
//    treats its own tree as the project root — and on case-sensitive
//    filesystems a case-folding mutant would silently scan the CONSUMER's
//    tree instead. This is the only layout where the two behaviors differ,
//    which is why the mutant survived every earlier check.
// --------------------------------------------------------------------------
{
	const parent = freshParent();
	const proj = join(parent, "consumer");
	// Deliberately mis-cased install directory.
	mkdirSync(join(proj, ".DevGate", "scripts", "lib"), { recursive: true });
	copyFileSync(join(scriptsDir, "run-tests.mjs"),
		join(proj, ".DevGate", "scripts", "run-tests.mjs"));
	copyFileSync(join(scriptsDir, "lib", "project-root.mjs"),
		join(proj, ".DevGate", "scripts", "lib", "project-root.mjs"));
	// Scope contract planted INSIDE the mis-cased dir: as a standalone tree
	// (the contract's verdict) the runner must find it there. If the marker
	// were case-folded, root would be <proj> and the contract lookup (root
	// first, devgateRoot second) would still find this file — the assertion
	// below does not turn on the contract, only on which tree gets scanned.
	cpSync(join(repoRoot, ".guardrails"), join(proj, ".DevGate", ".guardrails"), { recursive: true });
	// The consumer's own tests sit at the project level — findable ONLY by a
	// scanner that case-folds the marker name.
	mkdirSync(join(proj, "tests"), { recursive: true });
	for (let i = 1; i <= 2; i++) {
		writeFileSync(join(proj, "tests", `app_${i}.test.mjs`), PASSING_TEST);
	}
	const res = spawnSync(process.execPath,
		[join(proj, ".DevGate", "scripts", "run-tests.mjs")],
		{ encoding: "utf-8", cwd: proj });
	const out = (res.stdout ?? "") + (res.stderr ?? "");
	check("run-tests: a case-variant .DevGate directory is not the submodule marker",
		res.status !== 0 && /no test files discovered/.test(out) && countFiles(out) !== 2,
		`exit ${res.status}: ${JSON.stringify(out.slice(-200))}`);
}

// --------------------------------------------------------------------------
// 9. The contract consults NO filesystem. Checks 1-8 all assert a resolved
//    ROOT via scanner output, which leaves one implementation detail
//    unasserted: whether the answer came from layout or from a marker test.
//    The independent audit (2026-09-21) flagged a walk-up mutant as surviving;
//    investigating it showed the mutant it wrote is provably equivalent to the
//    contract on every layout the scanners can be installed in (its first probe
//    is join(devgateRoot, ".devgate"), which returns devgateRoot — exactly the
//    standalone branch — so it is a no-op rather than a real variant). The
//    genuinely dangerous shape, a walk-up starting ABOVE the scanner, is killed
//    by 8 checks. What no check covered is the property that makes the contract
//    cheap and total: projectRootFor is a pure function of its argument.
//
//    Asserted by calling the module directly with paths that do NOT exist. A
//    marker-based implementation (of any start point) answers these from the
//    filesystem and returns null-ish/undefined or walks to a real ancestor; a
//    layout implementation answers from the string alone. This is the one probe
//    a filesystem-consulting implementation cannot pass by accident, and it
//    costs no subprocess.
// --------------------------------------------------------------------------
{
	const probe = `
import { projectRootFor } from ${JSON.stringify(join(repoRoot, "scripts", "lib", "project-root.mjs"))};
const out = [];
out.push(projectRootFor("/nonexistent-aaa/bbb"));
out.push(projectRootFor("/nonexistent-aaa/bbb/.devgate"));
out.push(projectRootFor("/"));
out.push(projectRootFor("/nonexistent-aaa"));
console.log(JSON.stringify(out));
`;
	const res = spawnSync(process.execPath, ["--input-type=module", "-e", probe],
		{ encoding: "utf-8" });
	let got;
	try { got = JSON.parse((res.stdout ?? "").trim()); } catch { got = null; }
	const want = ["/nonexistent-aaa/bbb", "/nonexistent-aaa/bbb", "/", "/nonexistent-aaa"];
	check("project-root: resolves by path alone, never by touching the filesystem",
		Array.isArray(got) && got.length === 4 && got.every((v, i) => v === want[i]),
		`want ${JSON.stringify(want)}, got ${JSON.stringify(got)} (stderr: ${(res.stderr ?? "").slice(0, 160)})`);
}

for (const d of dirs) rmSync(d, { recursive: true, force: true });

if (failures) {
	console.error(`\n${failures} root-anchor check(s) failed`);
	process.exit(1);
}
console.log("\nall root-anchor checks passed");
