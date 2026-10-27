// Fixture tests for semantic-scan.mjs's project-overlay merge and
// SEMANTIC-005's module-scope exemption.
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
//   * SEMANTIC-005 used to demand module-scope bindings (ES imports, top-level
//     declarations) in every dependency array — the exact names
//     react-hooks/exhaustive-deps rejects as "unnecessary dependencies …
//     Outer scope values like 'X' aren't valid dependencies because mutating
//     them doesn't re-render". No array could satisfy both gates. Module
//     plumbing is exempt (matching the rule's own header claim); component-
//     scope values the callback reads remain required.
//   * Same conflict for host builtins: encodeURIComponent and friends are
//     frozen globals (verifiable on vbrainstorm 2026-10-27, VerifyEmail.tsx
//     where the effect builds a /verify-email?token= URL) — listing one in a
//     dependency array is an eslint "unnecessary dependency" warning, omitting
//     it used to be a SEMANTIC-005 finding. The EFFECT_GLOBALS set spells the
//     exempt host-globals class incompletely; these fixtures lock the ECMA-262
//     / web-platform builtins in it.
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

// --- 5. SEMANTIC-005 exempts module-scope bindings (ES imports, top-level) ---
// Pre-fix this fails: readSession (an ES import) and PAGE (a top-level const)
// were demanded in the dependency array — the exact names react-hooks/
// exhaustive-deps calls "unnecessary dependencies … Outer scope values …
// aren't valid dependencies because mutating them doesn't re-render the
// component". Listing them silences SEMANTIC-005 but fires the React lint;
// omitting them does the reverse. No array could win.
{
	const dir = mkdtempSync(join(tmpdir(), "devgate-sem-"));
	makeProject(dir, {
		"src/session.ts": "export function readSession() { return null; }\n",
		"src/list.ts": [
			'import { readSession } from "./session";',
			"const PAGE = 50;",
			"export function useList(logPath: string) {",
			"\tuseEffect(() => {",
			"\t\tvoid readSession();",
			"\t\tvoid PAGE;",
			"\t\tvoid logPath;",
			"\t}, [logPath]);",
			"}",
			"",
		].join("\n"),
	});
	const r = runScan(dir);
	check("module-scope: import + top-level const need not be listed",
		r.code === 0 && !r.err.includes("SEMANTIC-005"),
		r.err.slice(-300));
	check("module-scope: scan reports clean", r.out.includes("semantic scan clean"));
	cleanup(dir);
}

// --- 6. SEMANTIC-005 still demands component-scope values -------------------
// The exemption is module-scope ONLY. A value created inside the component
// (fetchData below) is exactly what a stale closure reads — omitting it stays
// a finding, or the fix above would disarm the rule.
{
	const dir = mkdtempSync(join(tmpdir(), "devgate-sem-"));
	makeProject(dir, {
		"src/comp.ts": [
			"export function useList(logPath: string) {",
			"\tconst fetchData = () => { void logPath; };",
			"\tuseEffect(() => {",
			"\t\tfetchData();",
			"\t}, []);",
			"}",
			"",
		].join("\n"),
	});
	const r = runScan(dir);
	check("component-scope: omitted local is still a finding",
		r.code === 1 && r.err.includes("SEMANTIC-005") && r.err.includes("fetchData"),
		r.err.slice(-300));
	cleanup(dir);
}

// --- 7. real consumer shape: ChatPane-style session effect ------------------
// The vbrainstorm ChatPane effect that started all this: reads an ES import
// class + a session reader, lists its props/callback/refs and nothing else.
// Pre-fix this demands ChatSession/readCommunitySession in the array; post-
// fix the exact array eslint accepts is clean here too.
{
	const dir = mkdtempSync(join(tmpdir(), "devgate-sem-"));
	makeProject(dir, {
		"src/chat-session.ts": "export class ChatSession { connect() {} close() {} }\n",
		"src/session.ts": "export function readCommunitySession() { return null; }\n",
		"src/chat-pane.ts": [
			'import { ChatSession } from "./chat-session";',
			'import { readCommunitySession } from "./session";',
			"export function useChat(spaceId: string, activeRoomId: string | null, refresh: () => void) {",
			"\tconst sessionRef = { current: null as ChatSession | null };",
			"\tuseEffect(() => {",
			"\t\tif (!activeRoomId) { sessionRef.current = null; return; }",
			"\t\tconst session = readCommunitySession();",
			"\t\tif (!session) return;",
			"\t\tconst chat = new ChatSession();",
			"\t\tsessionRef.current = chat;",
			"\t\tchat.connect();",
			"\t\trefresh();",
			"\t\treturn () => { sessionRef.current = null; chat.close(); };",
			"\t}, [spaceId, activeRoomId, refresh, sessionRef]);",
			"}",
			"",
		].join("\n"),
	});
	const r = runScan(dir);
	check("chat-pane shape: eslint-compatible array passes SEMANTIC-005",
		r.code === 0 && !r.err.includes("SEMANTIC-005"),
		r.err.slice(-300));
	cleanup(dir);
}

// --- 8. the no-dependency-array branch is unchanged --------------------------
{
	const dir = mkdtempSync(join(tmpdir(), "devgate-sem-"));
	makeProject(dir, {
		"src/tick.ts": "export function useTick() {\n\tuseEffect(() => { void 1; });\n}\n",
	});
	const r = runScan(dir);
	check("no-deps: missing dependency array still blocks",
		r.code === 1 && r.err.includes("no dependency array"),
		r.err.slice(-300));
	cleanup(dir);
}

// --- 9. host builtins need not be listed (encodeURIComponent et al.) ---------
// The VerifyEmail shape: an effect builds a URL with a frozen ECMA-262
// builtin. Pre-fix this demands encodeURIComponent in the array — the exact
// "unnecessary dependency: Outer scope values" warning eslint emits — so no
// array could satisfy both gates, same class as module plumbing (test 5).
// Media constructors (`new Audio()`, `new MediaMetadata()`, AudioContext.tsx)
// are the same frozen-host class and must stay exempt alongside them.
{
	const dir = mkdtempSync(join(tmpdir(), "devgate-sem-"));
	makeProject(dir, {
		"src/verify.ts": [
			"export function useVerify(token: string) {",
			"\tuseEffect(() => {",
			"\t\tif (!token) return;",
			"\t\tvoid encodeURIComponent(token);",
			"\t\tvoid new URLSearchParams({ token });",
			"\t\tvoid parseInt(token, 10);",
			"\t\tconst a = new Audio();",
			"\t\tvoid new MediaMetadata({ title: token });",
			"\t\ta.pause();",
			"\t}, [token]);",
			"}",
			"",
		].join("\n"),
	});
	const r = runScan(dir);
	check("host-globals: encodeURIComponent/URLSearchParams need not be listed",
		r.code === 0 && !r.err.includes("SEMANTIC-005"),
		r.err.slice(-300));
	check("host-globals: scan reports clean", r.out.includes("semantic scan clean"));
	cleanup(dir);
}

// --- 10. type-position identifiers are erased, not read ----------------------
// `e: MessageEvent` and `querySelector<HTMLIFrameElement>` name types, not
// runtime values — demanding them (vbrainstorm SettingsPanel/WritePost/Comments
// 2026-10-27) forced another dependency the React lint forbids. Runtime global
// constructors like `new MutationObserver()` still count (via EFFECT_GLOBALS).
{
	const dir = mkdtempSync(join(tmpdir(), "devgate-sem-"));
	makeProject(dir, {
		"src/types-effect.ts": [
			"export function useTheme() {",
			"\tuseEffect(() => {",
			"\t\tconst onMsg = (e: MessageEvent) => { void e; };",
			"\t\tconst el = document.querySelector<HTMLIFrameElement>('iframe');",
			"\t\tconst ob = new MutationObserver(() => {});",
			"\t\tob.observe(document.documentElement, { attributes: true });",
			"\t\twindow.addEventListener('message', onMsg);",
			"\t\tvoid el;",
			"\t\treturn () => { window.removeEventListener('message', onMsg); ob.disconnect(); };",
			"\t}, []);",
			"}",
			"",
		].join("\n"),
	});
	const r = runScan(dir);
	check("type-positions: MessageEvent/HTMLIFrameElement need not be listed",
		r.code === 0 && !r.err.includes("SEMANTIC-005"),
		r.err.slice(-300));
	check("type-positions: scan reports clean", r.out.includes("semantic scan clean"));
	cleanup(dir);
}

// --- 11. binding patterns bind targets only (audit cases C/D, 2026-10-27) -----
// `{ apiBase: API_BASE }` binds API_BASE — the property key is a lookup name.
// `{ a = helper() }` binds a — the initializer reads some OTHER binding.
// Pre-fix both leaked into moduleScope and wrongly exempted component-locals
// of the same spelling (C vs C2, D vs D2 on the audit matrix).
{
	const dir = mkdtempSync(join(tmpdir(), "devgate-sem-"));
	makeProject(dir, {
		"src/prop.ts": [
			"const config = { apiBase: 'x' };",
			"const { apiBase: API_BASE } = config;",
			"void API_BASE;",
			"export function useThing() {",
			"\tconst apiBase = 'y';",
			"\tuseEffect(() => { console.log(apiBase); }, []);",
			"}",
			"",
		].join("\n"),
		"src/def.ts": [
			"const config: Record<string, unknown> = {};",
			"const { a = someHelper() } = config;",
			"void a;",
			"export function useThing2() {",
			"\tconst someHelper = () => {};",
			"\tuseEffect(() => { someHelper(); }, []);",
			"}",
			"",
		].join("\n"),
	});
	const r = runScan(dir);
	check("binding-targets: property-key rename does not exempt a local",
		r.code === 1 && r.err.includes("apiBase"),
		r.err.slice(-300));
	check("binding-targets: initializer name does not exempt a local",
		r.err.includes("someHelper"),
		r.err.slice(-300));
	cleanup(dir);
}

// --- 12. `declare global` is merging, not a binding (audit case G) -----------
// Its `global` marker-name must not enter moduleScope — pre-fix it exempted a
// component-local named `global` (G vs G2 on the audit matrix).
{
	const dir = mkdtempSync(join(tmpdir(), "devgate-sem-"));
	makeProject(dir, {
		"src/glob.ts": [
			"declare global { interface Window { x: number } }",
			"export function useG() {",
			"\tconst global = 1;",
			"\tuseEffect(() => { console.log(global); }, []);",
			"}",
			"",
		].join("\n"),
	});
	const r = runScan(dir);
	check("declare-global: marker name does not exempt a local",
		r.code === 1 && r.err.includes("global"),
		r.err.slice(-300));
	cleanup(dir);
}

// --- 13. heritage expressions are runtime reads (audit cases I/L) ------------
// `class X extends Base {}` evaluates Base when the class is defined;
// `extends makeBase()` evaluates makeBase. ExpressionWithTypeArguments is a
// TypeNode, so the plain type-position check pre-fix hid these reads — while
// the `<T>` arguments really are erased and must stay exempt.
{
	const dir = mkdtempSync(join(tmpdir(), "devgate-sem-"));
	makeProject(dir, {
		"src/heritage.ts": [
			"export function useT() {",
			"\tconst Base = class {};",
			"\tconst makeBase = () => class {};",
			"\tuseEffect(() => {",
			"\t\tclass X extends Base {}",
			"\t\tclass Y extends makeBase() {}",
			"\t\tvoid new X(); void new Y();",
			"\t}, []);",
			"}",
			"",
		].join("\n"),
		"src/heritage-typearg.ts": [
			"export interface Shape { x: number }",
			"export function useU() {",
			"\tconst makeBase = <T,>() => class {};",
			"\tuseEffect(() => {",
			"\t\tclass Z extends makeBase<Shape>() {}",
			"\t\tvoid new Z();",
			"\t}, [makeBase]);",
			"}",
			"",
		].join("\n"),
	});
	const r = runScan(dir);
	check("heritage: extends Base is a required dependency",
		r.code === 1 && r.err.includes("Base"),
		r.err.slice(-300));
	check("heritage: extends makeBase() is a required dependency",
		r.err.includes("makeBase"),
		r.err.slice(-300));
	cleanup(dir);
}

console.log(failures === 0 ? "\nALL TESTS PASSED" : `\n${failures} TEST(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
