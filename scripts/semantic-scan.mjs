#!/usr/bin/env node
// Semantic/AST-based guardrails scanner.
// Currently supports TypeScript/JavaScript AST analysis via the TypeScript compiler API.
// Every other language's rule in semantic-rules.json ships enabled:false until
// its checker exists here — scripts/rules_check.py fails the hygiene gate when
// an enabled rule has no registered checker, so this header cannot again claim
// coverage the scanner does not have (rule-truth-01).
//
// SEMANTIC-001: detects Promise.then() chains that lack a .catch() handler.
// SEMANTIC-005: detects React useEffect effects with no dependency array, or
//               whose array omits values the callback reads.
//
// This scanner auto-detects the project root and scans TS/JS files there
// (not inside .devgate/ itself). If your project has no TypeScript/JavaScript,
// this script exits 0 with a "no matching files" message.
//
// Supports inline allow: // guardrails-allow <RULE-ID>: <reason>

import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { projectRootFor } from "./lib/project-root.mjs";

const devgateRoot = join(dirname(fileURLToPath(import.meta.url)), "..");

// Project root by LAYOUT CONTRACT (see scripts/lib/project-root.mjs). The old
// marker walk-up from .devgate's parent settled on shared directories above the
// checkout (e.g. a "git repos" folder carrying its own package.json) and scanned
// every sibling repo — thousands of foreign files evaluated by a gate that
// believed it was scanning DevGate. The exact figure moves as sibling repos
// grow (so it is not quoted as a constant), but the failure shape is stable:
// a root chosen by "nearest marker above me" can silently be the wrong tree.
// Same escape as run-tests.mjs had; same fix, one shared source.
// tests/test_scanner_root_anchor.mjs locks the contract.
const root = projectRootFor(devgateRoot);


function findScope() {
  // Scope contract resolves from the LAYOUT ROOT for BOTH layouts: a
  // standalone checkout (.guardrails/scope.json at the root) and a consumer
  // submodule (.devgate/.guardrails/scope.json). Never a walk-up from
  // process.cwd() — that can settle above the tree (root-anchor-01 class).
  for (const candidate of [join(root, ".guardrails", "scope.json"),
                           join(devgateRoot, ".guardrails", "scope.json")]) {
    if (existsSync(candidate)) return candidate;
  }
  return null;
}
// Scope contract is DATA (fw-scope-01): .guardrails/scope.json, shared by all gates.
const SKIP_DIRS = (() => {
  const scopePath = findScope();
  if (!scopePath) throw new Error("scope contract missing: .guardrails/scope.json");
  return JSON.parse(readFileSync(scopePath, "utf8")).skip_dirs;
})();

// Per-project scan scoping — same .guardrailsignore contract as
// guardrails-scan.mjs: one fnmatch glob per line ("*" crosses "/"), trailing
// "/" = directory prefix. Without this, archived trees and generated fixtures
// the project scoped out of the pattern gate still drove semantic-scan to
// require the typescript package (and fail) for files nobody maintains.
function loadIgnorePatterns(r) {
	const p = join(r, ".guardrailsignore");
	if (!existsSync(p)) return [];
	return readFileSync(p, "utf-8")
		.split("\n")
		.map((l) => l.trim())
		.filter((l) => l && !l.startsWith("#"));
}

const ignorePatterns = loadIgnorePatterns(root);

function rel(file) {
	return file.startsWith(root + "/") ? file.slice(root.length + 1) : file;
}

// Mirrors guardrails-scan.mjs globMatch: fnmatch "*" spans path separators,
// "**" is a globstar, "**/" also matches zero directories.
function globMatch(glob, path) {
	const P = "\x00GS\x00";
	let tmp = glob
		.replace(/\*\*\//g, P + "DSLASH" + P)
		.replace(/\*\*/g, P + "GLOBSTAR" + P)
		.replace(/\*/g, P + "STAR" + P)
		.replace(/\?/g, P + "QMARK" + P);
	tmp = tmp.replace(/[.+^${}()|[\]\\]/g, "\\$&");
	const pattern = tmp
		.replace(new RegExp(P + "DSLASH" + P, "g"), "(?:.*/)?")
		.replace(new RegExp(P + "GLOBSTAR" + P, "g"), ".*")
		.replace(new RegExp(P + "STAR" + P, "g"), ".*")
		.replace(new RegExp(P + "QMARK" + P, "g"), ".");
	return new RegExp("^" + pattern + "$").test(path);
}

function isIgnored(file) {
	if (ignorePatterns.length === 0) return false;
	const r = rel(file);
	const base = file.split("/").pop();
	return ignorePatterns.some((pat) =>
		pat.endsWith("/")
			? r.startsWith(pat) || r === pat.slice(0, -1)
			: globMatch(pat, r) || globMatch(pat, base),
	);
}

function walk(dir, acc = []) {
	if (!existsSync(dir)) return acc;
	for (const name of readdirSync(dir)) {
		const p = join(dir, name);
		if (statSync(p).isDirectory()) {
			if (!SKIP_DIRS.includes(name) && !isIgnored(p)) walk(p, acc);
		// .mjs/.cjs are load-bearing here, not an afterthought: DevGate's own
		// first-party modules are .mjs (8 tracked files, zero .js/.ts), so a
		// walk without them reported "no files, skipped" over the whole repo —
		// a permanently-empty gate, the S0 carry-forward's other horn.
		} else if ((name.endsWith(".ts") || name.endsWith(".tsx") || name.endsWith(".js") || name.endsWith(".jsx") || name.endsWith(".mjs") || name.endsWith(".cjs")) && !name.endsWith(".d.ts") && !name.endsWith(".test.ts") && !name.endsWith(".spec.ts") && !isIgnored(p)) {
			acc.push(p);
		}
	}
	return acc;
}

function collectFiles() {
	// Scan the project root for TS/JS files — NOT .devgate/ itself
	return walk(root);
}

function loadAllowLines(sourceText, ruleId) {
	const allowMap = new Map();
	const lines = sourceText.split("\n");
	const re = new RegExp(`guardrails-allow\\s+${ruleId}\\s*:\\s*(.+)`);
	for (let i = 0; i < lines.length; i++) {
		const m = lines[i].match(re);
		if (m) allowMap.set(i + 1, m[1].trim());
	}
	return allowMap;
}

function isChainHandled(thenCall) {
	let current = thenCall;
	while (true) {
		const parent = current.parent;
		if (!parent) return false;
		if (ts.isPropertyAccessExpression(parent)) {
			const propName = parent.name.text;
			if (propName === "catch") return true;
			if (propName === "then" || propName === "finally") {
				const grand = parent.parent;
				if (grand && ts.isCallExpression(grand)) { current = grand; continue; }
				return false;
			}
			return false;
		}
		if (ts.isAwaitExpression(parent)) return true;
		if (ts.isParenthesizedExpression(parent)) { current = parent; continue; }
		return false;
	}
}

function findUnhandledThenCalls(sourceFile) {
	const violations = [];
	function visit(node) {
		if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)) {
			const propName = node.expression.name.text;
			if (propName === "then") {
				if (node.arguments.length >= 2) { ts.forEachChild(node, visit); return; }
				if (!isChainHandled(node)) {
					const lineNum = sourceFile.getLineAndCharacterOfPosition(node.getStart()).line + 1;
					violations.push({ line: lineNum, message: "Promise chain missing .catch() handler" });
				}
			}
		}
		ts.forEachChild(node, visit);
	}
	visit(sourceFile);
	return violations;
}

// --- SEMANTIC-005: useEffect missing dependencies ---------------------------
// Conservative where the AST is ambiguous: deps passed as a variable, a
// non-identifier element (`[...base]`, `[user.id]`), or a non-function
// callback stay SILENT instead of guessed — design Q1 ships this rule at
// warning severity with the guardrails-allow escape, and a hook lint that
// fires on code it cannot actually analyze is how a gate trains people to
// ignore it. Known accepted FP class (also Q1): stable refs used as
// `ref.current` are flagged when the array omits them; annotate those.

// Values an effect reads without listing them: React, host globals, module
// plumbing, and state setters (useState/reducer setters are contract-stable).
const EFFECT_GLOBALS = new Set([
	"React", "console", "window", "document", "navigator", "location",
	"localStorage", "sessionStorage", "fetch", "setTimeout", "clearTimeout",
	"setInterval", "clearInterval", "requestAnimationFrame", "cancelAnimationFrame",
	"Math", "JSON", "Date", "Number", "String", "Boolean", "Array", "Object",
	"Promise", "Error", "globalThis", "process", "require", "module", "exports",
	"undefined", "NaN", "Infinity",
]);

const DECLARATION_KIND_NAMES = [
	"VariableDeclaration", "Parameter", "FunctionDeclaration", "ClassDeclaration",
	"FunctionExpression", "BindingElement",
];

// Resolved against ts.SyntaxKind at call time: `node.kind` is numeric, so a
// Set of strings would never match (it would read nested-arrow parameters as
// free references and flag them as missing dependencies).
function declarationNameOf(node) {
	const names = DECLARATION_KIND_NAMES;
	for (const n of names) {
		if (node.kind === ts.SyntaxKind[n]) return node.name;
	}
	return undefined;
}

// Every identifier a binding pattern introduces (`const {a, [b]: c} = …`).
function bindingIdentifiers(nameNode, out) {
	if (!nameNode) return;
	if (ts.isIdentifier(nameNode)) { out.add(nameNode.text); return; }
	ts.forEachChild(nameNode, (c) => bindingIdentifiers(c, out));
}

// Identifiers the callback READS, minus what it declares itself and minus
// property/key positions (`obj.prop` reads `obj`, never `prop`).
function freeIdentifiers(fn) {
	const declared = new Set();
	for (const p of fn.parameters) bindingIdentifiers(p.name, declared);
	function collect(node) {
		const name = declarationNameOf(node);
		if (name) bindingIdentifiers(name, declared);
		ts.forEachChild(node, collect);
	}
	collect(fn);

	const refs = new Set();
	function gather(node) {
		if (ts.isIdentifier(node)) {
			const parent = node.parent;
			const isDeclName = parent && declarationNameOf(parent) === node;
			const isProp = parent && ts.isPropertyAccessExpression(parent) && parent.name === node;
			const isKey = parent && ts.isPropertyAssignment(parent) && parent.name === node;
			if (!isDeclName && !isProp && !isKey) refs.add(node.text);
			return;
		}
		ts.forEachChild(node, gather);
	}
	gather(fn);
	for (const name of [...refs]) {
		if (declared.has(name) || EFFECT_GLOBALS.has(name) || /^set[A-Z]/.test(name)) {
			refs.delete(name);
		}
	}
	return refs;
}

function findEffectMissingDeps(sourceFile) {
	const violations = [];
	function lineOf(node) {
		return sourceFile.getLineAndCharacterOfPosition(node.getStart()).line + 1;
	}
	function analyze(call) {
		const cb = call.arguments[0];
		if (!cb || !(ts.isArrowFunction(cb) || ts.isFunctionExpression(cb))) return;
		const deps = call.arguments[1];
		if (!deps || (ts.isIdentifier(deps) && deps.text === "undefined")) {
			violations.push({
				line: lineOf(call),
				message: "useEffect has no dependency array — it re-runs after every render",
			});
			return;
		}
		if (!ts.isArrayLiteralExpression(deps)) return;
		if (deps.elements.some((e) => !ts.isIdentifier(e))) return;
		const provided = new Set(deps.elements.map((e) => e.text));
		const missing = [...freeIdentifiers(cb)].filter((n) => !provided.has(n)).sort();
		if (missing.length > 0) {
			violations.push({
				line: lineOf(call),
				message: `useEffect callback reads ${missing.join(", ")} but the dependency array omits ${missing.length === 1 ? "it" : "them"}`,
			});
		}
	}
	function visit(node) {
		if (ts.isCallExpression(node)) {
			const callee = node.expression;
			const isUseEffect =
				(ts.isIdentifier(callee) && callee.text === "useEffect") ||
				(ts.isPropertyAccessExpression(callee) && callee.name.text === "useEffect");
			if (isUseEffect) analyze(node);
		}
		ts.forEachChild(node, visit);
	}
	visit(sourceFile);
	return violations;
}

// The registry is the scanner's executable truth: rules_check.py compares
// semantic-rules.json's enabled ids against `--list-checkers` output, so an
// enabled rule with no checker fails hygiene instead of evaluating nothing.
const CHECKERS = {
	"SEMANTIC-001": findUnhandledThenCalls,
	"SEMANTIC-005": findEffectMissingDeps,
};

// The TypeScript compiler API is only needed when the project actually has
// TS/JS files to parse. A static import would crash every Rust/Python/Go
// consumer that never runs `npm install typescript` — load it lazily instead.
let ts;

async function main() {
	if (process.argv.includes("--list-checkers")) {
		// The hygiene gate's question ("which rules actually execute here?")
		// answered by the scanner itself, not by grepping its source.
		console.log(JSON.stringify(Object.keys(CHECKERS).sort()));
		process.exit(0);
	}
	const files = collectFiles();
	if (files.length === 0) {
		console.log("GUARDRAILS: semantic scan skipped (no TypeScript/JavaScript files found in project).");
		process.exit(0);
	}

	try {
		const mod = await import("typescript");
		ts = mod.default ?? mod;
	} catch {
		ts = null;
	}
	// typescript@7 ships as a CLI-only package (the compiler API moved off the
	// root export), so a bare `npm install typescript` loads fine but crashes
	// mid-scan with an opaque "Cannot read properties of undefined". Two honest
	// outcomes, never a silent pass: by default the gate FAILS with the
	// actionable pin ("you have TS/JS files but no parser" must not read as
	// "scan clean"); a project that knowingly cannot provide the parser sets
	// DEVGATE_SEMANTIC_REQUIRED=0 and gets an explicit SKIPPED line — the gate
	// list then says "skipped", not "green".
	if (!ts || typeof ts.createSourceFile !== "function" || !ts.ScriptTarget) {
		if (process.env.DEVGATE_SEMANTIC_REQUIRED === "0") {
			console.log(`GUARDRAILS: semantic scan SKIPPED — counted ${files.length} TS/JS file(s), evaluated NONE: the typescript compiler API is unavailable (DEVGATE_SEMANTIC_REQUIRED=0). Install with: npm install --no-save typescript@5 to actually run this gate.`);
			process.exit(0);
		}
		console.error(`GUARDRAILS: semantic scan found ${files.length} TS/JS file(s) but cannot load the typescript compiler API. The gate evaluated NOTHING — this is a tooling error, not a clean scan.`);
		console.error("Install it with: npm install --no-save typescript@5  (v7 dropped the root compiler API). To skip this gate explicitly instead, set DEVGATE_SEMANTIC_REQUIRED=0.");
		process.exit(1);
	}

	let totalViolations = 0;
	const rulesDoc = JSON.parse(readFileSync(
		join(devgateRoot, ".guardrails", "prevention-rules", "semantic-rules.json"),
		"utf8"));
	// Enabled AND registered: enabled-without-checker is rules_check.py's
	// failure (hygiene), while disabled rules are honest "not implemented yet".
	const activeRules = (rulesDoc.rules || []).filter((r) => r.enabled && CHECKERS[r.rule_id]);
	const activeIds = activeRules.map((r) => r.rule_id).join(", ");
	if (activeRules.length === 0) {
		console.log("GUARDRAILS: semantic scan clean (no enabled rule has a checker).");
		process.exit(0);
	}

	for (const file of files) {
		const sourceText = readFileSync(file, "utf-8");
		const relFile = file.startsWith(root + "/") ? file.slice(root.length + 1) : file;
		const sourceFile = ts.createSourceFile(file, sourceText, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);

		for (const rule of activeRules) {
			const allowLines = loadAllowLines(sourceText, rule.rule_id);
			const violations = CHECKERS[rule.rule_id](sourceFile);

			const reportedLines = new Set();
			for (const v of violations) {
				if (reportedLines.has(v.line)) continue;
				const reason = allowLines.get(v.line) || allowLines.get(v.line - 1);
				if (reason) { reportedLines.add(v.line); continue; }
				reportedLines.add(v.line);
				console.error(`[GUARDRAILS][${rule.rule_id}] ${relFile}:${v.line} — ${v.message}. ${rule.suggestion || "Fix the code"}, or annotate with // guardrails-allow ${rule.rule_id}: <reason>`);
				totalViolations++;
			}
		}
	}

	if (totalViolations > 0) {
		console.error(`\nGUARDRAILS: ${totalViolations} semantic violation(s) found (${activeIds}).`);
		process.exit(1);
	}
	console.log(`GUARDRAILS: semantic scan clean (${activeIds}).`);
}

// main() is async (lazy parser import) — route its rejections through the same
// error/exit contract the sync callers used to get from the try/catch.
main().catch((e) => { console.error("semantic-scan error:", e.message); process.exit(1); });
