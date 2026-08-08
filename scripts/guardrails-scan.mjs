#!/usr/bin/env node
// DevGate guardrails pattern scanner — language-agnostic.
// Loads .guardrails/prevention-rules/pattern-rules.json and scans source files
// for lines matching any enabled error/critical rule.
// Supports inline `// guardrails-allow RULE-ID: <reason>` annotations.

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const rulesPath = join(root, ".guardrails", "prevention-rules", "pattern-rules.json");

function loadRules() {
	const data = JSON.parse(readFileSync(rulesPath, "utf-8"));
	return data.rules.filter(
		(r) => r.enabled !== false &&
			["critical", "error"].includes(r.severity),
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
	const rel = file.startsWith(root + "/") ? file.slice(root.length + 1) : file;
	return globs.some((g) => globMatch(g, rel));
}

function walk(dir, acc = []) {
	for (const name of readdirSync(dir)) {
		const p = join(dir, name);
		if (statSync(p).isDirectory()) {
			if (!["node_modules", "dist", "target", ".git", ".claude", ".crew"].includes(name)) walk(p, acc);
		} else if (/\.(ts|js|py|rs|go|gd|java|kt|rb|php)$/.test(name) && !name.endsWith(".d.ts")) {
			acc.push(p);
		}
	}
	return acc;
}

function main() {
	const rules = loadRules();
	const files = [...walk(join(root, "src")), ...walk(join(root, "extensions")), ...walk(join(root, "scripts"))];
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
						console.error(`[GUARDRAILS][${rule.severity}] ${rule.rule_id} ${file}:${i + 1} — ${rule.message}`);
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
