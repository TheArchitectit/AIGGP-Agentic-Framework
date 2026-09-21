#!/usr/bin/env node
/**
 * run-tests.mjs — isolated per-file test runner (language-agnostic).
 *
 * Auto-detects test files by extension:
 *   .test.js / .spec.js  → node --test
 *   _test.py / test_*.py → pytest (if available)
 *   *_test.rs / tests/   → cargo test (if Cargo.toml exists)
 *
 * Each file runs in its OWN subprocess so failures never cascade.
 *
 * Env overrides:
 *   DEVGATE_TEST_TIMEOUT  per-file hard cap in ms (default 120000)
 *   DEVGATE_TEST_POOL     parallel worker count (default = CPU count, max 8)
 *   DEVGATE_TEST_HANG_MS  silence threshold before force-kill (default 10000)
 */

import { spawn } from "node:child_process";
import { readdirSync, statSync, mkdtempSync, rmSync, mkdirSync, existsSync } from "node:fs";
import { join, relative, basename, extname } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import os from "node:os";

import { projectRootFor } from "./lib/project-root.mjs";

const DEVGATE_ROOT = join(fileURLToPath(import.meta.url), "..", "..");

// Project root by LAYOUT CONTRACT (see scripts/lib/project-root.mjs), never a
// marker walk-up from an ancestor: the old findProjectRoot(resolve(root,".."))
// settled on any parent holding package.json/.git — scanning sibling repos in
// the directory above the checkout, discovering zero of DevGate's own tests,
// and still exiting 0. tests/test_scanner_root_anchor.mjs locks it.
const PROJECT_ROOT = projectRootFor(DEVGATE_ROOT);

const PER_FILE_TIMEOUT_MS = Number(process.env.DEVGATE_TEST_TIMEOUT ?? 120_000);
const HARD_CAP_MS = PER_FILE_TIMEOUT_MS + 10_000;
const SILENCE_MS = Number(process.env.DEVGATE_TEST_HANG_MS ?? 10_000);
const POOL = Math.max(1, Math.min(Number(process.env.DEVGATE_TEST_POOL ?? os.cpus().length), 8));

const SKIP_DIRS = ["node_modules", "dist", "target", ".git", ".claude", ".crew", "__pycache__", ".devgate", "vendor", "build", "out", ".next", ".nuxt", "venv", ".venv"];

// Test file patterns by language
function isTestFile(filename) {
	return (
		filename.endsWith(".test.js") ||
		filename.endsWith(".spec.js") ||
		filename.endsWith(".test.mjs") ||
		filename.endsWith(".test.ts") ||
		filename.endsWith("_test.py") ||
		filename.endsWith("_test.rs") ||
		filename.endsWith("_tests.rs") ||
		filename.startsWith("test_") && filename.endsWith(".py")
	);
}

// Serial lane: tests that share resources (ports, CPU)
const SERIAL_GLOB = /(?:^|\/)(?:dashboard|perf|budget|server|integration)[^/]*\.(test|spec)\.(js|mjs|ts|py)$/i;

function collectTestFiles(dir, acc = []) {
	if (!existsSync(dir)) return acc;
	for (const entry of readdirSync(dir)) {
		const full = join(dir, entry);
		const st = statSync(full);
		if (st.isDirectory()) {
			if (!SKIP_DIRS.includes(entry)) collectTestFiles(full, acc);
		} else if (isTestFile(entry)) {
			acc.push(full);
		}
	}
	return acc;
}

// Run a single test file using the appropriate runner
function runOne(file) {
	return new Promise((resolve) => {
		const start = Date.now();
		const ext = extname(file);
		const isPython = ext === ".py";
		const isRust = ext === ".rs";

		let cmd, args;
		if (isRust) {
			// Rust tests: run cargo test filtered to the test file's module.
			// *_test.rs files are compiled into cargo test binaries; we match by
			// the file stem (e.g. plugin_smoke_tests -> plugin_smoke_tests).
			cmd = "cargo";
			const stem = basename(file, ".rs");
			args = ["test", "--manifest-path", join(PROJECT_ROOT, "Cargo.toml"),
				"--", "--test-threads=1", stem];
		} else if (isPython) {
			cmd = "python3";
			args = ["-m", "pytest", "-v", "--tb=short", file];
		} else {
			// Node test runner for JS/TS
			cmd = process.execPath;
			args = ["--test", "--test-concurrency=1", "--test-reporter=tap",
				"--test-force-exit", `--test-timeout=${PER_FILE_TIMEOUT_MS}`, file];
		}

		const iso = mkdtempSync(join(tmpdir(), "dg-test-iso-"));
		mkdirSync(iso, { recursive: true });
		const env = { ...process.env };
		const child = spawn(cmd, args, { cwd: PROJECT_ROOT, env });

		let out = "";
		let tapDone = false;
		let graceTimer = null;
		let startedCount = 0;
		let completedCount = 0;
		let lastOutputAt = Date.now();

		const markTapDone = () => {
			if (tapDone) return;
			if (/^# pass\s+\d+/m.test(out) || /^=+ .* passed/m.test(out)) {
				tapDone = true;
				graceTimer = setTimeout(() => { if (!child.killed) child.kill("SIGKILL"); }, 1500);
			}
		};
		const onResult = (s) => {
			if (/^\s*(ok|not ok)\s+\d+/m.test(s)) completedCount++;
			if (/^# Subtest:/m.test(s)) startedCount++;
			if (/PASSED|FAILED|ERROR/m.test(s)) completedCount++;
		};

		const silenceTimer = setInterval(() => {
			if (tapDone || child.killed) return;
			if (startedCount > 0 && startedCount === completedCount &&
				Date.now() - lastOutputAt > SILENCE_MS) {
				child.kill("SIGKILL");
			}
		}, 1000);

		child.stdout.on("data", (b) => { const s = b.toString(); out += s; lastOutputAt = Date.now(); markTapDone(); onResult(s); });
		child.stderr.on("data", (b) => { const s = b.toString(); out += s; lastOutputAt = Date.now(); markTapDone(); onResult(s); });

		let timedOut = false;
		const timer = setTimeout(() => { timedOut = true; child.kill("SIGKILL"); }, HARD_CAP_MS);

		let stdoutEnded = false, stderrEnded = false, closeCode = undefined, drainTimer;
		const tryResolve = (code, force) => {
			if (!force && (!stdoutEnded || !stderrEnded)) return;
			clearTimeout(timer); clearInterval(silenceTimer);
			if (graceTimer) clearTimeout(graceTimer);
			try { rmSync(iso, { recursive: true, force: true }); } catch { /* best-effort */ }
			const pass = (out.match(/^# pass\s+(\d+)/m) || out.match(/(\d+)\s+passed/))?.[1];
			const fail = (out.match(/^# fail\s+(\d+)/m) || out.match(/(\d+)\s+failed/))?.[1];
			const okCount = (out.match(/^ok\s+\d+/gm) || []).length;
			const notOkCount = (out.match(/^not ok\s+\d+/gm) || []).length;
			resolve({
				file: relative(PROJECT_ROOT, file), code, timedOut, tapDone, okCount,
				hung: okCount > 0 && code !== 0 && !timedOut,
				pass: pass ? Number(pass) : okCount,
				fail: fail ? Number(fail) : notOkCount,
				ms: Date.now() - start,
				snippet: out.split("\n").filter((l) => /^# (fail|not ok|FAILED|ERROR)/.test(l)).slice(0, 3).join("  "),
			});
		};
		const checkDrain = () => {
			if (closeCode === undefined) return;
			if (stdoutEnded && stderrEnded) { clearTimeout(drainTimer); tryResolve(closeCode, closeCode === null); }
		};
		child.on("close", (code) => {
			if (code === null) { tryResolve(code, true); return; }
			closeCode = code;
			drainTimer = setTimeout(() => tryResolve(code, true), 1000);
			checkDrain();
		});
		child.stdout.on("end", () => { stdoutEnded = true; checkDrain(); });
		child.stderr.on("end", () => { stderrEnded = true; checkDrain(); });
	});
}

function fmt(ms) { return (ms / 1000).toFixed(1) + "s"; }

async function main() {
	// Collect test files from the project root (not .devgate/)
	const distDir = join(PROJECT_ROOT, "dist");
	const testDir = join(PROJECT_ROOT, "test");
	const testsDir = join(PROJECT_ROOT, "tests");
	const srcDir = join(PROJECT_ROOT, "src");

	const all = [
		...collectTestFiles(distDir),
		...collectTestFiles(testDir),
		...collectTestFiles(testsDir),
		...collectTestFiles(srcDir),
	].sort();

	// Deduplicate
	const seen = new Set();
	const unique = all.filter(f => { if (seen.has(f)) return false; seen.add(f); return true; });

	// Zero discovery is an ERROR, never a silent green. A runner that collects
	// no test files and exits 0 is indistinguishable from one that ran them all
	// and passed — and the historical cause of zero discovery here was precisely
	// a root-anchoring escape (the walk-up settled on a directory above the
	// checkout that had no `tests/`). The 2026-09-20 audit's mutation battery
	// survives a layout-only fix; this is the non-vacuity contract that does
	// not. DEVGATE_ALLOW_NO_TESTS=1 is the one honest opt-out (a project with
	// genuinely no tests) and it prints a loud skip line, never a green total.
	if (unique.length === 0) {
		if (process.env.DEVGATE_ALLOW_NO_TESTS === "1") {
			console.error("run-tests: no test files discovered — SKIPPED via DEVGATE_ALLOW_NO_TESTS=1 (this is a skip, not a pass).");
			process.exit(0);
		}
		console.error(`run-tests: no test files discovered under ${PROJECT_ROOT} (checked dist/, test/, tests/, src/). ` +
			"This is a FAILURE, not a pass: a runner that evaluates nothing must not look green. " +
			"If a project genuinely has no tests, set DEVGATE_ALLOW_NO_TESTS=1 to record an explicit skip.");
		process.exit(1);
	}

	const serial = unique.filter((f) => SERIAL_GLOB.test(f));
	const rest = unique.filter((f) => !SERIAL_GLOB.test(f));

	let totalPass = 0, totalFail = 0;
	const failed = [];
	const wallStart = Date.now();

	async function runAndReport(f) {
		console.error(`▶ ${relative(PROJECT_ROOT, f)}`);
		const r = await runOne(f);
		totalPass += r.pass; totalFail += r.fail;
		const crashedBeforeTests = r.code !== 0 && !r.tapDone && r.okCount === 0 && r.pass === 0;
		const ok = !r.timedOut && r.fail === 0 && !crashedBeforeTests;
		const mark = ok ? "✓" : "✗";
		const tail = r.fail > 0 ? `  ${r.snippet}` : r.timedOut ? "  TIMED OUT" :
			r.hung ? "  (tests passed; exit-hung)" : crashedBeforeTests ? `  (crashed, code ${r.code})` : "";
		console.error(`${mark} ${relative(PROJECT_ROOT, f)}  (${r.pass} pass / ${r.fail} fail, ${fmt(r.ms)})${tail}`);
		if (!ok) failed.push(r);
		return r;
	}

	console.error(`\n▶ ${rest.length} test files in parallel (pool=${POOL}), ${PER_FILE_TIMEOUT_MS / 1000}s cap/file`);
	let i = 0;
	async function worker() { while (i < rest.length) { const f = rest[i++]; await runAndReport(f); } }
	await Promise.all(Array.from({ length: Math.min(POOL, rest.length) }, worker));

	if (serial.length) {
		console.error(`\n▶ serial lane (${serial.length} files)`);
		for (const f of serial) await runAndReport(f);
	}

	const flakes = [];
	if (failed.length) {
		console.error(`\n▶ solo adjudication (${failed.length} files; re-running failures solo)`);
		for (const r of failed.slice()) {
			console.error(`▶ solo: ${r.file}`);
			const solo = await runOne(join(PROJECT_ROOT, r.file));
			// A solo re-run only clears a failure if it GENUINELY succeeded:
			// zero failures AND a clean exit. A file that crashed before any
			// test ran (collection error, missing import) emits no "N failed"
			// lines — fail parses as 0 — and must NOT be adjudicated as a
			// flake. That masking is a silent-success failure mode.
			const soloClean = solo.fail === 0 && solo.code === 0 && !solo.timedOut;
			if (soloClean) {
				totalFail -= r.fail; flakes.push(r.file);
				failed.splice(failed.indexOf(r), 1);
				console.error(`✓ solo: ${r.file}  (${solo.pass} pass / 0 fail, ${fmt(solo.ms)})  (flake)`);
			} else {
				const why = solo.timedOut ? "TIMED OUT" :
					solo.code !== 0 ? `crashed, code ${solo.code}` : `${solo.fail} fail`;
				console.error(`✗ solo: ${r.file}  (${solo.pass} pass / ${solo.fail} fail — ${why})`);
			}
		}
	}

	const wall = fmt(Date.now() - wallStart);
	console.error(`\nTOTAL: ${totalPass} passed, ${totalFail} failed across ${unique.length} files in ${wall}`);
	if (flakes.length) { console.error("FLAKY FILES:"); for (const f of flakes) console.error(`  - ${f}`); }
	if (failed.length) {
		console.error("FAILED FILES:");
		for (const r of failed) console.error(`  - ${r.file}  (code ${r.code ?? "signal"}${r.timedOut ? ", TIMED OUT" : ""})`);
		process.exit(1);
	}
	process.exit(0);
}

main().catch((e) => { console.error(e); process.exit(1); });
