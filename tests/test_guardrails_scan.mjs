// Fixture tests for guardrails-scan.mjs — locks the corrected gate semantics.
//
// History these tests prevent from regressing:
//   * The glob matcher anchored "*" to a single path segment, so every
//     glob-scoped rule (*.go, *.py, …) silently matched nothing but
//     project-root files — the pattern scan reported "clean" on trees full of
//     violations. A gate that silently stops firing is worse than no gate, so
//     these tests assert the gate FIRES on known violations and stays SILENT
//     on the cases that must not trip it.
//   * forbidden_context was never honored, so rules fired on their own
//     suppression examples.
//   * There was no project-level ignore, so frozen/archived trees failed the
//     gate with violations nobody is allowed to fix.
//
// Run: node tests/test_guardrails_scan.mjs
import { execFileSync } from "node:child_process";
import { copyFileSync, mkdirSync, mkdtempSync, rmSync, writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const scanner = join(repoRoot, "scripts", "guardrails-scan.mjs");
const rules = join(repoRoot, ".guardrails", "prevention-rules", "pattern-rules.json");

let failures = 0;
function check(name, cond, detail = "") {
	if (cond) console.log(`ok - ${name}`);
	else { failures++; console.error(`FAIL - ${name}${detail ? `: ${detail}` : ""}`); }
}

function makeProject(dir, files) {
	mkdirSync(join(dir, ".devgate", "scripts"), { recursive: true });
	mkdirSync(join(dir, ".devgate", ".guardrails", "prevention-rules"), { recursive: true });
	copyFileSync(scanner, join(dir, ".devgate", "scripts", "guardrails-scan.mjs"));
	copyFileSync(rules, join(dir, ".devgate", ".guardrails", "prevention-rules", "pattern-rules.json"));
	writeFileSync(join(dir, "go.mod"), "module example.com/fixture\n\ngo 1.21\n");
	for (const [rel, content] of Object.entries(files)) {
		const p = join(dir, rel);
		mkdirSync(dirname(p), { recursive: true });
		writeFileSync(p, content);
	}
}

function runScan(dir) {
	// Must exec the COPY inside the fixture — the scanner resolves its project
	// root from its own file location, not from cwd.
	const local = join(dir, ".devgate", "scripts", "guardrails-scan.mjs");
	try {
		execFileSync("node", [local], { cwd: dir, encoding: "utf-8", stdio: ["ignore", "pipe", "pipe"] });
		return { code: 0, out: "", err: "" };
	} catch (e) {
		return { code: e.status ?? 1, out: e.stdout ?? "", err: e.stderr ?? "" };
	}
}

// --- 1. glob-scoped rules fire on NESTED files (the core regression) --------
const dir1 = mkdtempSync(join(tmpdir(), "devgate-scan-"));
makeProject(dir1, {
	"internal/spawners/spawners.go": "package spawners\n\nvar x = string(rune('0' + 3))\n",
	"main.go": "package main\n\nfunc main() {}\n",
});
let r = runScan(dir1);
check("nested *.go violation blocks the scan", r.code === 1);
check("finding names the nested file and rule", r.err.includes("PREVENT-030") && r.err.includes("internal/spawners/spawners.go"));
rmSync(dir1, { recursive: true, force: true });

// --- 2. exclude_glob keeps the rule quiet on matching files -----------------
// Same violating line in a test file and a production file: the *_test.go
// exclusion must silence exactly one of them.
const dir2 = mkdtempSync(join(tmpdir(), "devgate-scan-"));
makeProject(dir2, {
	"internal/store/store.go": "package store\n\nfunc Save() {\n\tx, _ := loadRecord()\n\t_ = x\n}\n",
	"internal/store/store_test.go": "package store\n\nfunc TestSave(t *T) {\n\tx, _ := loadRecord()\n\t_ = x\n}\n",
});
r = runScan(dir2);
check("PREVENT-009 fires on production discard", r.err.includes("internal/store/store.go"));
check("PREVENT-009 excludes *_test.go", !r.err.includes("internal/store/store_test.go"));
rmSync(dir2, { recursive: true, force: true });

// --- 3. guardrails-allow annotation (same line) suppresses ------------------
const dir3 = mkdtempSync(join(tmpdir(), "devgate-scan-"));
makeProject(dir3, {
	"internal/spawners/spawners.go": "package spawners\n\nvar x = string(rune('0' + 3)) // guardrails-allow PREVENT-030: fixture\n",
});
r = runScan(dir3);
check("allow annotation suppresses", r.code === 0);
rmSync(dir3, { recursive: true, force: true });

// --- 4. forbidden_context suppresses the hit --------------------------------
const dir4 = mkdtempSync(join(tmpdir(), "devgate-scan-"));
makeProject(dir4, {
	"internal/py/bare.py": "try:\n    pass\nexcept Exception:\n    pass\n",
});
r = runScan(dir4);
check("forbidden_context (Exception) suppresses PREVENT-007", !r.err.includes("PREVENT-007"));
rmSync(dir4, { recursive: true, force: true });

// --- 5. .guardrailsignore scopes the walk -----------------------------------
const dir5 = mkdtempSync(join(tmpdir(), "devgate-scan-"));
makeProject(dir5, {
	"archive/python/bare.py": "try:\n    pass\nexcept:\n    pass\n",
	"pkg/keep.py": "try:\n    pass\nexcept:\n    pass\n",
});
writeFileSync(join(dir5, ".guardrailsignore"), "# frozen legacy\narchive/\n");
r = runScan(dir5);
check(".guardrailsignore excludes archive/, keeps pkg/", r.code === 1 && !r.err.includes("archive/python/bare.py") && r.err.includes("pkg/keep.py"));
rmSync(dir5, { recursive: true, force: true });

// --- 6. project overlay MERGES over the bundled baseline --------------------
// A game repo carries its own .guardrails/prevention-rules/pattern-rules.json
// next to the .devgate/ submodule. Baseline rules must keep firing, overlay
// rules must fire too, and an overlay entry sharing a baseline rule_id must
// REPLACE it (retuned severity/message) rather than double-report.
const dir6 = mkdtempSync(join(tmpdir(), "devgate-scan-"));
makeProject(dir6, {
	"internal/spawners/spawners.go": "package spawners\n\nvar x = string(rune('0' + 3))\n",
	"model/player.rs": "fn nearest(q: &[Enemy]) -> f32 {\n\tfor e in &q { distance(e) }\n}\n",
});
mkdirSync(join(dir6, ".guardrails", "prevention-rules"), { recursive: true });
writeFileSync(join(dir6, ".guardrails", "prevention-rules", "pattern-rules.json"), JSON.stringify({
	version: "1.0.0",
	rules: [
		// NEW id → appended: fires on the .rs file only the overlay knows about
		{ rule_id: "PREVENT-XI-001", name: "linear nearest scan", enabled: true, pattern: "for .* in &.*\\{", severity: "error", file_glob: ["*.rs"], message: "O(n) nearest scan", suggestion: "spatial hash" },
		// SAME id as bundled PREVENT-030 → replaces it: severity downgraded to warning here
		{ rule_id: "PREVENT-030", name: "rune digit", enabled: true, pattern: "string\\(rune\\('0'\\s*\\+", severity: "warning", file_glob: ["*.go"], message: "retuned by project overlay", suggestion: "simplify" },
	],
}));
r = runScan(dir6);
check("overlay: new rule_id fires (PREVENT-XI-001)", r.err.includes("PREVENT-XI-001"));
check("overlay: merge banner shown", r.out.includes("overlay merged"));
// If same-id REPLACED worked: the .go hit is a warning (0 errors from 030) and
// the .rs hit is the one error. Replacement failure would show 2 violations.
check("overlay: same-id entry REPLACED severity (error→warning)", r.err.includes("1 warning(s)") && r.err.includes("1 violation(s)"));
check("overlay: replaced entry uses overlay message", r.err.includes("retuned by project overlay"));
check("overlay: scan blocks on the appended rule", r.code === 1);
rmSync(dir6, { recursive: true, force: true });

// --- 7. explicit GUARDRAILS_RULES env collapses to a single file ------------
const dir7 = mkdtempSync(join(tmpdir(), "devgate-scan-"));
makeProject(dir7, {
	"internal/spawners/spawners.go": "package spawners\n\nvar x = string(rune('0' + 3))\n",
	"model/player.rs": "fn nearest(q: &[Enemy]) -> f32 {\n\tfor e in &q { distance(e) }\n}\n",
});
mkdirSync(join(dir7, ".guardrails", "prevention-rules"), { recursive: true });
writeFileSync(join(dir7, ".guardrails", "prevention-rules", "pattern-rules.json"), JSON.stringify({
	rules: [{ rule_id: "PREVENT-XI-001", enabled: true, pattern: "for .* in &.*\\{", severity: "error", file_glob: ["*.rs"], message: "overlay only", suggestion: "-" }],
}));
{
	const local = join(dir7, ".devgate", "scripts", "guardrails-scan.mjs");
	let res;
	try {
		const out = execFileSync("node", [local], { cwd: dir7, encoding: "utf-8", stdio: ["ignore", "pipe", "pipe"], env: { ...process.env, GUARDRAILS_RULES: join(dir7, ".guardrails", "prevention-rules", "pattern-rules.json") } });
		res = { code: 0, out: out ?? "", err: "" };
	} catch (e) {
		res = { code: e.status ?? 1, out: e.stdout ?? "", err: e.stderr ?? "" };
	}
	check("env override: overlay-only rule fires", res.code === 1 && res.err.includes("PREVENT-XI-001"));
	check("env override: bundled baseline NOT merged (030 silent)", !res.err.includes("PREVENT-030"));
}
rmSync(dir7, { recursive: true, force: true });

// --- 8. Python-side semantics agree: file_glob + allow + ignore -------------
// (game_regression.py is exercised by tests/test_game_regression.py,
//  gate_overlay.py by tests/test_gate_overlay.py)

console.log(failures === 0 ? "\nALL TESTS PASSED" : `\n${failures} TEST(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
