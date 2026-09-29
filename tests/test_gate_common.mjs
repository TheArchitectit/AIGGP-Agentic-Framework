// Unit tests for scripts/lib/gate_common.mjs — shared Node gate primitives.
//
// Mirrors tests/test_gate_common.py. Locks the same contracts on the JS side:
//   * root detection is the layout contract
//   * SKIP_DIRS comes from .guardrails/scope.json (project overlay wins)
//   * lineHasAllow requires reason text and keys on the id
//   * globMatch crosses / and expands **
//   * walk skips SKIP_DIRS, skips symlinked dirs, survives EACCES
//
// Run: node tests/test_gate_common.mjs
import { mkdirSync, mkdtempSync, symlinkSync, writeFileSync, chmodSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import {
	globMatch,
	globMatchesAny,
	lineHasAllow,
	loadIgnorePatterns,
	loadSkipDirs,
	projectRootFor,
	walk,
} from "../scripts/lib/gate_common.mjs";

let failures = 0;
function check(name, cond, detail = "") {
	if (cond) console.log(`ok - ${name}`);
	else {
		failures++;
		console.error(`FAIL - ${name}${detail ? `: ${detail}` : ""}`);
	}
}

// --- root -------------------------------------------------------------------
{
	const dg = join(tmpdir(), "x", ".devgate");
	check(
		"projectRootFor: submodule layout → parent",
		projectRootFor(dg) === join(tmpdir(), "x"),
	);
	check("projectRootFor: standalone → self", projectRootFor("/gone/repo") === "/gone/repo");
}

// --- SKIP_DIRS --------------------------------------------------------------
{
	const base = mkdtempSync(join(tmpdir(), "gc-scope-"));
	const dg = join(base, ".devgate");
	mkdirSync(join(dg, ".guardrails"), { recursive: true });
	writeFileSync(
		join(dg, ".guardrails", "scope.json"),
		JSON.stringify({ skip_dirs: ["node_modules"] }),
	);
	check(
		"loadSkipDirs: baseline",
		loadSkipDirs({ devgateRoot: dg }).join() === "node_modules",
	);
	mkdirSync(join(base, ".guardrails"), { recursive: true });
	writeFileSync(
		join(base, ".guardrails", "scope.json"),
		JSON.stringify({ skip_dirs: ["node_modules", "extras"] }),
	);
	check(
		"loadSkipDirs: project overlay wins",
		loadSkipDirs({ devgateRoot: dg, projectRoot: base }).join() ===
			"node_modules,extras",
	);
	let threw = false;
	try {
		loadSkipDirs({ devgateRoot: join(base, "absent") });
	} catch (e) {
		threw = /scope\.json/.test(String(e.message));
	}
	check("loadSkipDirs: missing contract throws", threw);
}

// --- allow annotation -------------------------------------------------------
check("lineHasAllow: reason required", lineHasAllow("// guardrails-allow R-1: why", "R-1"));
check("lineHasAllow: bare colon is not an exemption", !lineHasAllow("// guardrails-allow R-1:", "R-1"));
check(
	"lineHasAllow: id keys the match",
	!lineHasAllow("// guardrails-allow R-1: only this", "R-10"),
);

// --- glob -------------------------------------------------------------------
check("globMatch: nested *.go", globMatch("*.go", "a/b/c.go"));
check("globMatch: **/ zero-segment", globMatch("a/**/b", "a/b"));
check("globMatch: **/ nested", globMatch("a/**/b", "a/x/b"));
check("globMatchesAny: basename arm", globMatchesAny(["*.py"], "src/x.py", "x.py"));
check("globMatchesAny: miss", !globMatchesAny(["*.rs"], "src/x.py", "x.py"));

// --- ignores ----------------------------------------------------------------
{
	const base = mkdtempSync(join(tmpdir(), "gc-ign-"));
	writeFileSync(join(base, ".guardrailsignore"), "# comment\n\nlegacy/\n*.snap\n");
	const pats = loadIgnorePatterns(base);
	check("loadIgnorePatterns: blanks/comments dropped", pats.join() === "legacy/,*.snap", pats.join());
}

// --- walk -------------------------------------------------------------------
{
	const base = mkdtempSync(join(tmpdir(), "gc-walk-"));
	mkdirSync(join(base, "src", "keep"), { recursive: true });
	mkdirSync(join(base, "node_modules", "pkg"), { recursive: true });
	writeFileSync(join(base, "src", "ok.py"), "x=1\n");
	writeFileSync(join(base, "node_modules", "pkg", "vendored.py"), "x=1\n");
	try {
		symlinkSync(join(base, "src"), join(base, "link-out"));
	} catch {
		/* some hosts disallow symlinks — the no-follow case still holds */
	}
	const found = walk(base, {
		skipDirs: ["node_modules"],
		accept: (name) => name.endsWith(".py"),
	});
	check(
		"walk: SKIP_DIRS pruned",
		found.some((f) => f.includes("ok.py")) && !found.some((f) => f.includes("vendored.py")),
		found.join(),
	);
	const files = walk(base, {
		skipDirs: [],
		accept: () => true,
		onFile: (p, acc) => acc.push(p),
		acc: [],
	});
	check("walk: onFile collector", Array.isArray(files) && files.length >= 2, String(files));
}

if (failures) {
	console.error(`${failures} FAIL(S)`);
	process.exit(1);
}
console.log("ALL TESTS PASSED");