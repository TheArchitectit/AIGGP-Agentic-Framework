// // spec: fw-scope-01, root-anchor-01
// Shared Node gate primitives — the JS home for the logic every scanner needs
// (scripts/lib/project-root.mjs is the root contract alone; this is the wider
// set). Python home: scripts/gate_common.py.
//
// Extracted 2026-09-28 (consolidate-shared-gate-logic) because guardrails-scan
// and semantic-scan carried verbatim copies of globMatch and near-copies of
// the walk / skip-dir / allow-annotation logic, so a fix ported poorly.
//
//   projectRootFor(devgateRoot)     layout-contract project root
//   loadSkipDirs({devgateRoot})     .guardrails/scope.json (project overlay wins)
//   globMatch(glob, path)           fnmatch-compatible, * crosses /
//   globMatchesAny(globs, rel, base)
//   lineHasAllow(line, id)          guardrails-allow <ID>: <reason>
//   loadIgnorePatterns(root)        .guardrailsignore
//   walk(dir, opts)                 EACCES-safe, no symlinked dirs, SKIP_DIRS

import { basename, dirname, join } from "node:path";
import { existsSync, lstatSync, readdirSync, readFileSync } from "node:fs";

import { projectRootFor } from "./project-root.mjs";

export { projectRootFor };

export function loadSkipDirs({ devgateRoot, projectRoot }) {
	for (const candidate of [
		projectRoot ? join(projectRoot, ".guardrails", "scope.json") : null,
		devgateRoot ? join(devgateRoot, ".guardrails", "scope.json") : null,
	]) {
		if (candidate && existsSync(candidate)) {
			const dirs = JSON.parse(readFileSync(candidate, "utf8")).skip_dirs;
			if (!Array.isArray(dirs)) {
				throw new Error(`${candidate}: skip_dirs must be a list`);
			}
			return dirs;
		}
	}
	throw new Error(
		"scope contract missing: .guardrails/scope.json (under the project root or .devgate/)",
	);
}

// fnmatch-compatible translation: "*" spans path separators (".*"), which
// is how "*.go" reaches nested files — the Python gates (gate_common.glob_matches)
// match with fnmatch, whose "*" already crosses "/". The old "[^/]*" anchored
// "*" to a single segment, so glob-scoped rules silently matched nothing but
// project-root files. "**" stays a globstar (".*") and "**/" additionally
// matches zero directories, mirroring _expand_globstars.
export function globMatch(glob, path) {
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

export function globMatchesAny(globs, rel, base) {
	// Parity with regression_diff.py / gate_common.glob_matches: basename OR path.
	return globs.some((g) => globMatch(g, rel) || globMatch(g, base));
}

export function lineHasAllow(line, id) {
	// Reason text required — identical to gate_common.line_has_allow and
	// guardrails-scan's historical matcher (FAIL-9231181d).
	return new RegExp(`guardrails-allow\\s+${id}\\s*:\\s*\\S`).test(line);
}

// One fnmatch glob per line ("*" crosses "/", same semantics as rule globs);
// trailing "/" = directory prefix. Blank lines and '#' comments ignored.
export function loadIgnorePatterns(root) {
	const p = join(root, ".guardrailsignore");
	if (!existsSync(p)) return [];
	return readFileSync(p, "utf-8")
		.split("\n")
		.map((l) => l.trim())
		.filter((l) => l && !l.startsWith("#"));
}

/**
 * Walk a directory tree for source files.
 * @param {string} dir
 * @param {{skipDirs: string[]|ReadonlyArray<string>, accept: (name: string, path: string) => boolean, isIgnored?: (path: string) => boolean, onFile?: (path: string, acc: any) => void, acc?: any[]}} opts
 */
export function walk(dir, opts) {
	const { skipDirs, accept, isIgnored = () => false, onFile } = opts;
	// Shared accumulator: recursive calls pass this same opts object, so the
	// default must live on opts (a per-call ``acc = []`` default would allocate
	// a fresh array at every directory and drop every finding).
	if (opts.acc === undefined) opts.acc = [];
	const acc = opts.acc;
	let entries;
	try {
		entries = readdirSync(dir);
	} catch {
		return acc; // unreadable directory (EACCES etc.) — skipped, not fatal
	}
	for (const name of entries) {
		const p = join(dir, name);
		let st;
		try {
			st = lstatSync(p);
		} catch {
			continue;
		}
		if (st.isDirectory()) {
			// Symlinked directories are never descended: no cycle, no escape
			// outside the resolved project root.
			if (st.isSymbolicLink()) continue;
			if (!skipDirs.includes(name) && !isIgnored(p)) {
				walk(p, opts);
			}
		} else if (accept(name, p) && !isIgnored(p)) {
			if (onFile) onFile(p, acc);
			else acc.push(p);
		}
	}
	return acc;
}

export { basename, dirname };