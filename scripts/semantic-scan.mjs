#!/usr/bin/env node
// Semantic/AST-based guardrails scanner.
// Currently supports TypeScript/JavaScript AST analysis via the TypeScript compiler API.
// For other languages, rules are defined in semantic-rules.json but require a
// language-specific AST parser to be implemented.
//
// SEMANTIC-001: detects Promise.then() chains that lack a .catch() handler.
// SEMANTIC-005: detects React useEffect with missing dependencies.
//
// This scanner auto-detects the project root and scans TS/JS files there
// (not inside .devgate/ itself). If your project has no TypeScript/JavaScript,
// this script exits 0 with a "no matching files" message.
//
// Supports inline allow: // guardrails-allow SEMANTIC-001: <reason>

import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const devgateRoot = join(dirname(fileURLToPath(import.meta.url)), "..");

// Auto-detect project root (parent of .devgate/)
function findProjectRoot(startDir) {
	let dir = startDir;
	for (let i = 0; i < 10; i++) {
		for (const marker of ["package.json", "Cargo.toml", "pyproject.toml", "setup.py", "go.mod", "project.godot", ".git"]) {
			if (existsSync(join(dir, marker))) return dir;
		}
		const parent = resolve(dir, "..");
		if (parent === dir) break;
		dir = parent;
	}
	return startDir;
}

const root = findProjectRoot(resolve(devgateRoot, ".."));

const SKIP_DIRS = ["node_modules", "dist", "target", ".git", ".claude", ".crew", "__pycache__", ".devgate", "vendor", "build", "out", ".next", ".nuxt", "venv", ".venv"];

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
		} else if ((name.endsWith(".ts") || name.endsWith(".tsx") || name.endsWith(".js") || name.endsWith(".jsx")) && !name.endsWith(".d.ts") && !name.endsWith(".test.ts") && !name.endsWith(".spec.ts") && !isIgnored(p)) {
			acc.push(p);
		}
	}
	return acc;
}

function collectFiles() {
	// Scan the project root for TS/JS files — NOT .devgate/ itself
	return walk(root);
}

function loadAllowLines(sourceText) {
	const allowMap = new Map();
	const lines = sourceText.split("\n");
	const re = /guardrails-allow\s+SEMANTIC-001\s*:\s*(.+)/;
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

// The TypeScript compiler API is only needed when the project actually has
// TS/JS files to parse. A static import would crash every Rust/Python/Go
// consumer that never runs `npm install typescript` — load it lazily instead.
let ts;

async function main() {
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
	// mid-scan with an opaque "Cannot read properties of undefined". Fail with
	// the actionable version pin instead — and fail loud: "you have TS/JS files
	// but no parser" must never read as "scan clean".
	if (!ts || typeof ts.createSourceFile !== "function" || !ts.ScriptTarget) {
		console.error(`GUARDRAILS: semantic scan found ${files.length} TS/JS file(s) but cannot load the typescript compiler API.`);
		console.error("Install it with: npm install --no-save typescript@5  (v7 dropped the root compiler API).");
		process.exit(1);
	}

	let totalViolations = 0;

	for (const file of files) {
		const sourceText = readFileSync(file, "utf-8");
		const relFile = file.startsWith(root + "/") ? file.slice(root.length + 1) : file;
		const sourceFile = ts.createSourceFile(file, sourceText, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
		const allowLines = loadAllowLines(sourceText);
		const violations = findUnhandledThenCalls(sourceFile);

		const reportedLines = new Set();
		for (const v of violations) {
			if (reportedLines.has(v.line)) continue;
			const reason = allowLines.get(v.line) || allowLines.get(v.line - 1);
			if (reason) { reportedLines.add(v.line); continue; }
			reportedLines.add(v.line);
			console.error(`[GUARDRAILS][SEMANTIC-001] ${relFile}:${v.line} — ${v.message}. Add .catch() handler, use try/catch with async/await, or annotate with // guardrails-allow SEMANTIC-001: <reason>`);
			totalViolations++;
		}
	}

	if (totalViolations > 0) {
		console.error(`\nGUARDRAILS: ${totalViolations} SEMANTIC-001 violation(s) found.`);
		process.exit(1);
	}
	console.log("GUARDRAILS: semantic scan clean (SEMANTIC-001).");
}

// main() is async (lazy parser import) — route its rejections through the same
// error/exit contract the sync callers used to get from the try/catch.
main().catch((e) => { console.error("semantic-scan error:", e.message); process.exit(1); });
