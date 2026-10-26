// Fixture tests for semantic-scan.mjs's project-overlay merge.
//
// History these tests prevent from regressing:
//   * semantic-scan.mjs loaded ONLY the bundled `.devgate/.guardrails/
//     prevention-rules/semantic-rules.json` and never consulted the project
//     overlay at `<project>/.guardrails/prevention-rules/semantic-rules.json`,
//     while guardrails-scan.mjs has merged that overlay since the overlay
//     contract landed (gate_overlay.py: overlay wins on rule_id collision).
//     A consumer (verified live on vbrainstorm 2026-10-26) therefore could not
//     retune or disable a semantic rule from the project overlay at all — the
//     one gate the overlay contract could not reach. "A gate that cannot go
//     green is a defect"; so is a gate a project cannot tune without forking
//     the submodule.
//   * The merge must MERGE, not replace: an overlay entry for SEMANTIC-001
//     must leave SEMANTIC-005 armed. And an overlay entry that replaces a rule
//     must actually replace it — its `suggestion` (the only rule-doc field the
//     finding line prints, next to the checker's own message) must show up in
//     the finding.
//
// Note on `message`: finding text comes from the CHECKER (it carries dynamic
// detail, e.g. SEMANTIC-005's missing names), not from rule.message. The
// observable overlay surface is `enabled` + `suggestion`, which is what these
// tests pin.
//
// Run: node tests/test_semantic_scan.mjs
import { execFileSync, spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const scanner = join(repoRoot, "scripts", "semantic-scan.mjs");
const rules = join(repoRoot, ".guardrails", "prevention-rules", "semantic-rules.json");

// Fixture cleanup must not throw (same contract as test_guardrails_scan.mjs:
// a leftover temp dir is a warning, never a truncated suite).
function cleanup(dir) {
	try {
		rmSync(dir, { recursive: true, force: true, maxRetries: 10, retryDelay: 50 });
	} catch (e) {
		console.warn(`warn - could not remove fixture ${dir}: ${e.code || e.message}`);
	}
}

let failures = 0;
function check(name, cond, detail = "") {
	if (cond) console.log(`ok - ${name}`);
	else { failures++; console.error(`FAIL - ${name}${detail ? `: ${detail}` : ""}`); }
}

// The scanner lazy-imports the typescript compiler API. The test lane never
// installs it (only self-gates does), so this suite provisions the same pin at
// the repo root on first run and links it into each fixture: bare
// `import("typescript")` from <fixture>/.devgate/scripts/ resolves up through
// <fixture>/node_modules. A fixture whose parser is missing would make the
// scanner fail-closed on a tooling error and every assertion below would be
// measuring that, not the overlay merge.
function ensureTypescript() {
	const tsDir = join(repoRoot, "node_modules", "typescript");
	if (existsSync(join(tsDir, "package.json"))) return tsDir;
	console.log("installing typescript@5 at repo root (semantic-scan parser pin)...");
	execFileSync("npm", ["install", "--no-save", "--no-audit", "--no-fund", "typescript@5"],
		{ cwd: repoRoot, stdio: "pipe" });
	return tsDir;
}

function linkParser(dir, tsDir) {
	const nm = join(dir, "node_modules");
	mkdirSync(nm, { recursive: true });
	const target = join(nm, "typescript");
	try {
		symlinkSync(tsDir, target, process.platform === "win32" ? "junction" : "dir");
	} catch {
		// Sandboxes that forbid symlinks: a CJS shim that re-exports the real
		// compiler package by absolute path — import("typescript") lands here
		// either way.
		mkdirSync(target, { recursive: true });
		writeFileSync(join(target, "package.json"),
			JSON.stringify({ name: "typescript", main: "index.js" }));
		writeFileSync(join(target, "index.js"),
			`module.exports = require(${JSON.stringify(join(tsDir, "lib", "typescript.js"))});\n`);
	}
}

const tsDir = ensureTypescript();

// Submodule layout fixture: <dir>/.devgate/ carries the scanner + its lib +
// scope + bundled rules; <dir>/.guardrails/ holds the project overlay under
// test. Must exec the COPY inside the fixture — the scanner resolves its
// project root from its own file location, not from cwd.
function makeProject(dir, files, overlayRules) {
	mkdirSync(join(dir, ".devgate", "scripts", "lib"), { recursive: true });
	mkdirSync(join(dir, ".devgate", ".guardrails", "prevention-rules"), { recursive: true });
	copyFileSync(scanner, join(dir, ".devgate", "scripts", "semantic-scan.mjs"));
	copyFileSync(join(repoRoot, "scripts", "lib", "project-root.mjs"),
		join(dir, ".devgate", "scripts", "lib", "project-root.mjs"));
	copyFileSync(join(repoRoot, "scripts", "lib", "gate_common.mjs"),
		join(dir, ".devgate", "scripts", "lib", "gate_common.mjs"));
	copyFileSync(join(repoRoot, ".guardrails", "scope.json"),
		join(dir, ".devgate", ".guardrails", "scope.json"));
	copyFileSync(rules, join(dir, ".devgate", ".guardrails", "prevention-rules", "semantic-rules.json"));
	if (overlayRules) {
		const p = join(dir, ".guardrails", "prevention-rules", "semantic-rules.json");
		mkdirSync(dirname(p), { recursive: true });
		writeFileSync(p, JSON.stringify({ rules: overlayRules }, null, "\t"));
	}
	linkParser(dir, tsDir);
	for (const [rel, content] of Object.entries(files)) {
		const p = join(dir, rel);
		mkdirSync(dirname(p), { recursive: true });
		writeFileSync(p, content);
	}
}

function runScan(dir, scannerPath = join(dir, ".devgate", "scripts", "semantic-scan.mjs")) {
	const res = spawnSync("node", [scannerPath], { cwd: dir, encoding: "utf-8" });
	return { code: res.status ?? 1, out: res.stdout ?? "", err: res.stderr ?? "" };
}

// One unhandled .then() — SEMANTIC-001's exact shape (1 arg, chain not
// handled). No useEffect in the file, so SEMANTIC-005 stays silent and every
// count below is SEMANTIC-001's alone.
const TRIP = "export function main() {\n\tdoWork().then(() => {});\n}\n";

// --- 1. baseline-only control: the checker fires without any overlay ----------
{
	const dir = mkdtempSync(join(tmpdir(), "devgate-sem-"));
	makeProject(dir, { "src/app.ts": TRIP });
	const r = runScan(dir);
	check("baseline: unhandled .then() blocks the scan", r.code === 1);
	check("baseline: finding names the file and rule",
		r.err.includes("SEMANTIC-001") && r.err.includes("src/app.ts"));
	check("baseline: exactly one violation", r.err.includes("1 semantic violation(s) found"));
	cleanup(dir);
}

// --- 2. overlay DISABLES a rule (enabled:false) and the merge keeps the rest --
// Same fixture, plus an overlay entry disabling SEMANTIC-001. The merge must
// honor it (exit 0, no SEMANTIC-001 finding) while SEMANTIC-005 — untouched by
// the overlay — stays armed in the active-rule summary. Pre-fix this fails:
// the scanner never read the overlay and still reported the violation.
{
	const dir = mkdtempSync(join(tmpdir(), "devgate-sem-"));
	makeProject(dir, { "src/app.ts": TRIP }, [
		{ rule_id: "SEMANTIC-001", name: "Unhandled promise rejection", enabled: false,
			language: "javascript", message: "disabled by project overlay",
			severity: "warning", suggestion: "n/a" },
	]);
	const r = runScan(dir);
	check("overlay: disabled rule no longer fires", r.code === 0 && !r.err.includes("SEMANTIC-001"));
	check("overlay: untouched SEMANTIC-005 stays armed", r.out.includes("SEMANTIC-005"));
	check("overlay: merge banner shown", r.out.includes("overlay merged"));
	cleanup(dir);
}

// --- 3. overlay REPLACES a rule entry: its suggestion reaches the finding -----
// rule.message is NOT the finding text (the checker's message is — it carries
// dynamic detail), so the observable replacement surface is `suggestion`.
// Pre-fix this fails: the bundled suggestion is printed no matter what the
// overlay says.
{
	const dir = mkdtempSync(join(tmpdir(), "devgate-sem-"));
	makeProject(dir, { "src/app.ts": TRIP }, [
		{ rule_id: "SEMANTIC-001", name: "Unhandled promise rejection", enabled: true,
			language: "javascript", message: "Promise chain missing .catch() handler",
			severity: "warning", suggestion: "OVERLAY_SUGGESTION_SENTINEL" },
	]);
	const r = runScan(dir);
	check("overlay: replaced entry fires", r.code === 1 && r.err.includes("SEMANTIC-001"));
	check("overlay: finding carries the overlay suggestion",
		r.err.includes("OVERLAY_SUGGESTION_SENTINEL"),
		r.err.slice(-300));
	check("overlay: bundled suggestion superseded",
		!r.err.includes("Add .catch() handler or use try/catch with async/await"));
	cleanup(dir);
}

// --- 4. standalone self-overlay is a no-op, not a double-merge ---------------
// DevGate running on its own repo: project root IS the devgate root, so the
// "overlay" path resolves to the bundled rules file itself. Reading it twice
// must not duplicate rules — a duplicated rule reports the same finding twice
// ("2 semantic violation(s)" for one line) and would make self-scan counts lie.
{
	const dir = mkdtempSync(join(tmpdir(), "devgate-sem-"));
	mkdirSync(join(dir, "scripts", "lib"), { recursive: true });
	mkdirSync(join(dir, ".guardrails", "prevention-rules"), { recursive: true });
	copyFileSync(scanner, join(dir, "scripts", "semantic-scan.mjs"));
	copyFileSync(join(repoRoot, "scripts", "lib", "project-root.mjs"),
		join(dir, "scripts", "lib", "project-root.mjs"));
	copyFileSync(join(repoRoot, "scripts", "lib", "gate_common.mjs"),
		join(dir, "scripts", "lib", "gate_common.mjs"));
	copyFileSync(join(repoRoot, ".guardrails", "scope.json"),
		join(dir, ".guardrails", "scope.json"));
	copyFileSync(rules, join(dir, ".guardrails", "prevention-rules", "semantic-rules.json"));
	linkParser(dir, tsDir);
	writeFileSync(join(dir, "app.ts"), TRIP);
	const r = runScan(dir, join(dir, "scripts", "semantic-scan.mjs"));
	check("standalone: self-overlay reports the finding once",
		r.err.includes("1 semantic violation(s) found"),
		r.err.slice(-300));
	check("standalone: no overlay-merge banner for the self-file",
		!r.out.includes("overlay merged"));
	cleanup(dir);
}

console.log(failures === 0 ? "\nALL TESTS PASSED" : `\n${failures} TEST(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
