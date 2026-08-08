#!/usr/bin/env node
// DevGate guardrails pattern scanner — language-agnostic.
// Scans the PARENT project's source files (not DevGate's own directory).
// Loads .guardrails/prevention-rules/pattern-rules.json and checks all source
// files against enabled error/critical rules.
// Supports inline `// guardrails-allow RULE-ID: <reason>` annotations.

import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, dirname, resolve, basename } from "node:path";
import { fileURLToPath } from "node:url";

// DevGate root (where this script lives — .devgate/scripts/)
const devgateRoot = join(dirname(fileURLToPath(import.meta.url)), "..");

// Project root = parent of DevGate directory (e.g. ../ from .devgate/)
// Auto-detect: walk up until we find a package.json, Cargo.toml, pyproject.toml,
// go.mod, project.godot, or .git — that's the project root.
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

const projectRoot = findProjectRoot(resolve(devgateRoot, ".."));
const rulesPath = join(devgateRoot, ".guardrails", "prevention-rules", "pattern-rules.json");

// Source file extensions to scan (language-agnostic)
const SOURCE_EXTENSIONS = [".ts", ".js", ".py", ".rs", ".go", ".gd", ".java", ".kt", ".rb", ".php", ".jsx", ".tsx"];

// Directories to skip (DevGate's own dir + common non-source dirs)
const SKIP_DIRS = ["node_modules", "dist", "target", ".git", ".claude", ".crew", "__pycache__", ".devgate", "vendor", "build", "out", ".next", ".nuxt", "venv", ".venv", "egg-info"];

function loadRules() {
	const data = JSON.parse(readFileSync(rulesPath, "utf-8"));
	return data.rules.filter(
		(r) => r.enabled !== false && ["critical", "error"].includes(r.severity),
	);
}

function globMatch(glob, path) {
	const P = "\x00GS\x00";
	let tmp = glob
		.replace(/\*\*\//g, P + "DSLASH" + P)
		.replace(/\*\*/g, P + "GLOBSTAR" + P)
		.replace(/\*/g, P + "STAR" + P)
		.replace(/\?/g, P + "QMARK" + P);
	tmp = tmp.replace(/[.+^${}()|[\]\\]/g, "\\$&");
	let pattern = tmp
		.replace(new RegExp(P + "DSLASH" + P, "g"), "(?:.+/)?")
		.replace(new RegExp(P + "GLOBSTAR" + P, "g"), ".*")
		.replace(new RegExp(P + "STAR" + P, "g"), "[^/]*")
		.replace(new RegExp(P + "QMARK" + P, "g"), ".");
	return new RegExp("^" + pattern + "$").test(path);
}

function ruleAppliesTo(rule, file) {
	const globs = rule.file_glob;
	if (!Array.isArray(globs) || globs.length === 0) return true;
	const rel = file.startsWith(projectRoot + "/") ? file.slice(projectRoot.length + 1) : file;
	return globs.some((g) => globMatch(g, rel));
}

function walk(dir, acc = []) {
	if (!existsSync(dir)) return acc;
	for (const name of readdirSync(dir)) {
		const p = join(dir, name);
		const st = statSync(p);
		if (st.isDirectory()) {
			if (!SKIP_DIRS.includes(name)) walk(p, acc);
		} else {
			const ext = "." + name.split(".").pop();
			if (SOURCE_EXTENSIONS.includes(ext) && !name.endsWith(".d.ts")) {
				acc.push(p);
			}
		}
	}
	return acc;
}

function main() {
	const rules = loadRules();
	const files = walk(projectRoot);
	let violations = 0;
	for (const file of files) {
		const lines = readFileSync(file, "utf-8").split("\n");
		lines.forEach((line, i) => {
			for (const rule of rules) {
				if (!ruleAppliesTo(rule, file)) continue;
				const allow = new RegExp(`guardrails-allow\\s+${rule.rule_id}\\s*:\\s*\\S`);
				if (allow.test(line)) continue;
				try {
					if (new RegExp(rule.pattern).test(line)) {
						const rel = file.startsWith(projectRoot + "/") ? file.slice(projectRoot.length + 1) : file;
						console.error(`[GUARDRAILS][${rule.severity}] ${rule.rule_id} ${rel}:${i + 1} — ${rule.message}`);
						violations++;
					}
				} catch { /* ignore bad regex */ }
			}
		});
	}
	if (violations > 0) {
		console.error(`\nGUARDRAILS: ${violations} violation(s) found.`);
		process.exit(1);
	}
	console.log("GUARDRAILS: pattern scan clean.");
}

try { main(); } catch (e) { console.error("guardrails-scan error:", e.message); process.exit(1); }
