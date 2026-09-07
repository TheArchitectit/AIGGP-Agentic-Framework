#!/usr/bin/env node
// DevGate guardrails pattern scanner — language-agnostic.
// Scans the PARENT project's source files (not DevGate's own directory).
// Loads .guardrails/prevention-rules/pattern-rules.json and checks all source
// files against enabled error/critical rules.
// Supports inline `// guardrails-allow RULE-ID: <reason>` annotations.

import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, dirname, resolve, basename } from "node:path";
import { fileURLToPath } from "node:url";

// DevGate root (where this script lives — <project>/.devgate/)
const devgateRoot = join(dirname(fileURLToPath(import.meta.url)), "..");

// Project root is the directory that CONTAINS the .devgate/ submodule — by
// layout contract, never an ancestor of it. The old implementation walked UP
// from .devgate's parent looking for a marker file, so a clean submodule
// checkout (whose parent has no go.mod yet) or a scanner run from inside the
// DevGate repo itself escaped to a grandparent like /mnt/data/git — scanning
// every sibling repo. DevGate standalone IS its own project.
const isSubmoduleLayout = basename(devgateRoot) === ".devgate";
const projectRoot = isSubmoduleLayout ? resolve(devgateRoot, "..") : devgateRoot;
const rulesPath = join(devgateRoot, ".guardrails", "prevention-rules", "pattern-rules.json");

// Source file extensions to scan (language-agnostic)
const SOURCE_EXTENSIONS = [".ts", ".js", ".py", ".rs", ".go", ".gd", ".java", ".kt", ".rb", ".php", ".jsx", ".tsx"];

// Directories to skip (DevGate's own dir + common non-source dirs)
const SKIP_DIRS = ["node_modules", "dist", "target", ".git", ".claude", ".crew", "__pycache__", ".devgate", "vendor", "build", "out", ".next", ".nuxt", "venv", ".venv", "egg-info"];

function loadRules() {
	const data = JSON.parse(readFileSync(rulesPath, "utf-8"));
	return data.rules.filter(
		(r) => r.enabled !== false && ["critical", "error", "warning"].includes(r.severity),
	);
}

function globMatch(glob, path) {
	// fnmatch-compatible translation: "*" spans path separators (".*"), which
	// is how "*.go" reaches nested files — the Python gates (regression_diff.py
	// glob_matches) match with fnmatch, whose "*" already crosses "/". The old
	// "[^/]*" anchored "*" to a single segment, so glob-scoped rules silently
	// matched nothing but project-root files. "**" stays a globstar (".*") and
	// "**/" additionally matches zero directories, mirroring _expand_globstars.
	const P = "\x00GS\x00";
	let tmp = glob
		.replace(/\*\*\//g, P + "DSLASH" + P)
		.replace(/\*\*/g, P + "GLOBSTAR" + P)
		.replace(/\*/g, P + "STAR" + P)
		.replace(/\?/g, P + "QMARK" + P);
	tmp = tmp.replace(/[.+^${}()|[\]\\]/g, "\\$&");
	let pattern = tmp
		.replace(new RegExp(P + "DSLASH" + P, "g"), "(?:.*/)?")
		.replace(new RegExp(P + "GLOBSTAR" + P, "g"), ".*")
		.replace(new RegExp(P + "STAR" + P, "g"), ".*")
		.replace(new RegExp(P + "QMARK" + P, "g"), ".");
	return new RegExp("^" + pattern + "$").test(path);
}

function globMatchesAny(globs, rel, base) {
	// Parity with regression_diff.py glob_matches: basename OR relative path.
	return globs.some((g) => globMatch(g, rel) || globMatch(g, base));
}

function ruleAppliesTo(rule, file) {
	const globs = rule.file_glob;
	if (!Array.isArray(globs) || globs.length === 0) return true;
	const rel = file.startsWith(projectRoot + "/") ? file.slice(projectRoot.length + 1) : file;
	// A bare-extension glob like "*.go" must reach nested files, not just the
	// project root — without the basename arm, "*.go" anchored to "[^/]*" matches
	// nothing nested and every glob-scoped rule is silently dead on a real tree.
	if (!globMatchesAny(globs, rel, basename(file))) return false;
	const excludes = rule.exclude_glob;
	if (Array.isArray(excludes) && excludes.length > 0 && globMatchesAny(excludes, rel, basename(file))) return false;
	return true;
}

// Per-project scoping the gate can't know — archived legacy trees, generated
// fixtures, anything that must not fail the gate. One fnmatch glob per line
// ("*" crosses "/", same semantics as rule globs); trailing "/" = directory
// prefix. Blank lines and '#' comments ignored.
function loadIgnorePatterns(root) {
	const p = join(root, ".guardrailsignore");
	if (!existsSync(p)) return [];
	return readFileSync(p, "utf-8")
		.split("\n")
		.map((l) => l.trim())
		.filter((l) => l && !l.startsWith("#"));
}

function relTo(root, file) {
	return file.startsWith(root + "/") ? file.slice(root.length + 1) : file;
}

function isIgnored(file, root, patterns) {
	if (patterns.length === 0) return false;
	const rel = relTo(root, file);
	const base = basename(file);
	return patterns.some((pat) =>
		pat.endsWith("/")
			? rel.startsWith(pat) || rel === pat.slice(0, -1)
			: globMatch(pat, rel) || globMatch(pat, base),
	);
}

function walk(dir, acc = [], ignorePatterns = []) {
	if (!existsSync(dir)) return acc;
	for (const name of readdirSync(dir)) {
		const p = join(dir, name);
		const st = statSync(p);
		if (st.isDirectory()) {
			if (!SKIP_DIRS.includes(name) && !isIgnored(p, projectRoot, ignorePatterns)) walk(p, acc, ignorePatterns);
		} else {
			const ext = "." + name.split(".").pop();
			if (SOURCE_EXTENSIONS.includes(ext) && !name.endsWith(".d.ts") && !isIgnored(p, projectRoot, ignorePatterns)) {
				acc.push(p);
			}
		}
	}
	return acc;
}

function main() {
	const rules = loadRules();
	const ignorePatterns = loadIgnorePatterns(projectRoot);
	if (ignorePatterns.length > 0) console.log(`GUARDRAILS: honoring ${ignorePatterns.length} .guardrailsignore entr(y/ies)`);
	const files = walk(projectRoot, [], ignorePatterns);
	let violations = 0;
	let warnings = 0;
	for (const file of files) {
		const lines = readFileSync(file, "utf-8").split("\n");
		lines.forEach((line, i) => {
			for (const rule of rules) {
				if (!ruleAppliesTo(rule, file)) continue;
				const allow = new RegExp(`guardrails-allow\\s+${rule.rule_id}\\s*:\\s*\\S`);
				if (allow.test(line)) continue;
				try {
					if (new RegExp(rule.pattern).test(line)) {
						// forbidden_context suppresses the hit when the same line
						// carries its documented safe usage — same rule as
						// regression_check.py's check_diff_against_patterns. Without
						// this, info rules like PREVENT-020 (TODO without ticket)
						// fire on their own suppression examples.
						if (rule.forbidden_context && new RegExp(rule.forbidden_context).test(line)) continue;
						const rel = file.startsWith(projectRoot + "/") ? file.slice(projectRoot.length + 1) : file;
						console.error(`[GUARDRAILS][${rule.severity}] ${rule.rule_id} ${rel}:${i + 1} — ${rule.message}`);
						if (rule.severity === "warning") {
							warnings++;
						} else {
							violations++;
						}
					}
				} catch { /* ignore bad regex */ }
			}
		});
	}
	if (warnings > 0) {
		console.error(`\nGUARDRAILS: ${warnings} warning(s) (non-blocking).`);
	}
	if (violations > 0) {
		console.error(`GUARDRAILS: ${violations} violation(s) found.`);
		process.exit(1);
	}
	console.log("GUARDRAILS: pattern scan clean.");
}

try { main(); } catch (e) { console.error("guardrails-scan error:", e.message); process.exit(1); }
