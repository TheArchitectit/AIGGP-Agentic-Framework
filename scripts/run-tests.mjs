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
import { readdirSync, lstatSync, mkdtempSync, rmSync, existsSync } from "node:fs";
import { join, relative, resolve, basename, extname, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import os from "node:os";

const DEVGATE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

// Project root is the directory that CONTAINS the .devgate/ submodule — by
// layout contract, never an ancestor of it. The old implementation walked UP
// from .devgate's parent looking for a marker file and returned the walk's
// start directory when none was found — which on a standalone DevGate clone
// is the repo's PARENT: discovery found none of dist/test/tests/src and the
// runner reported "0 passed, 0 failed across 0 files", exit 0, while the
// repo's own tests sat unrun (the flagship silent-success failure mode, in
// the runner that exists to prevent it). DevGate standalone IS its own
// project — same contract as guardrails-scan.mjs.
const isSubmoduleLayout = basename(DEVGATE_ROOT) === ".devgate";
const PROJECT_ROOT = isSubmoduleLayout ? resolve(DEVGATE_ROOT, "..") : DEVGATE_ROOT;

const PER_FILE_TIMEOUT_MS = Number(process.env.DEVGATE_TEST_TIMEOUT ?? 120_000);
const HARD_CAP_MS = PER_FILE_TIMEOUT_MS + 10_000;
const SILENCE_MS = Number(process.env.DEVGATE_TEST_HANG_MS ?? 10_000);
const POOL = Math.max(1, Math.min(Number(process.env.DEVGATE_TEST_POOL ?? os.cpus().length), 8));

const SKIP_DIRS = ["node_modules", "dist", "target", ".git", ".claude", ".crew", "__pycache__", ".devgate", "vendor", "build", "out", ".next", ".nuxt", "venv", ".venv"];

// Test file patterns by language. Covers both naming conventions per
// ecosystem: suffix style (.test.js / .spec.mjs / .test.tsx …) and the
// pytest/cargo prefix style (test_*.py, test_*.mjs — the repo's own JS
// fixture suite is test_guardrails_scan.mjs and was invisible to this
// runner until the prefix forms were added).
function isTestFile(filename) {
	const base = filename.toLowerCase();
	return (
		base.endsWith(".test.js") ||
		base.endsWith(".spec.js") ||
		base.endsWith(".test.mjs") ||
		base.endsWith(".spec.mjs") ||
		base.endsWith(".test.ts") ||
		base.endsWith(".spec.ts") ||
		base.endsWith(".test.tsx") ||
		base.endsWith(".spec.tsx") ||
		base.endsWith("_test.py") ||
		base.endsWith("_test.rs") ||
		base.endsWith("_tests.rs") ||
		(base.startsWith("test_") && base.endsWith(".py"))
	);
}
// Prefix-style JS suites (test_*.mjs / test_*.js) — separate guard so the
// Python pytest prefix rule above stays byte-comparable to its own tests.
// tests/test_guardrails_scan.mjs is the repo's strongest scanner suite and
// was executed by NOTHING until this form existed (audit finding, QA-adjacent).
function isPrefixTestFile(filename) {
	const base = filename.toLowerCase();
	return base.startsWith("test_") && (base.endsWith(".mjs") || base.endsWith(".js"));
}

// Serial lane: tests that share resources (ports, CPU). Matches both the
// dotted JS convention (perf.test.js) and the pytest underscore convention
// (perf_test.py) — before this, serial-unsafe Python tests ran in the
// parallel pool because the regex required a ".test."/" .spec." middle dot.
const SERIAL_GLOB = /(?:^|\/)(?:dashboard|perf|budget|server|integration)[^/]*(?:\.(?:test|spec)\.(?:js|mjs|cjs|ts|tsx)|_test\.py)$/i;

function collectTestFiles(dir, acc = []) {
	if (!existsSync(dir)) return acc;
	let entries;
	try {
		entries = readdirSync(dir);
	} catch {
		return acc; // unreadable directory — skipped, not fatal
	}
	for (const entry of entries) {
		const full = join(dir, entry);
		let st;
		try {
			st = lstatSync(full);
		} catch {
			continue;
		}
		if (st.isDirectory()) {
			// Symlinked directories are never descended (cycle/escape guard).
			if (st.isSymbolicLink()) continue;
			if (!SKIP_DIRS.includes(entry)) collectTestFiles(full, acc);
		} else if (st.isFile() && (isTestFile(entry) || isPrefixTestFile(entry))) {
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
			// Rust tests: select the integration-test TARGET by file stem.
			// `cargo test -- <stem>` matches test FUNCTION names, not files —
			// an integration file whose functions don't contain the stem ran
			// zero tests and cargo exited 0 ("0 passed"), so the file reported
			// ✓ while testing nothing (QA C4). `--test <stem>` names the
			// target itself; a file that is not a cargo target now fails loud
			// (no test target named <stem>) instead of passing vacuously.
			cmd = "cargo";
			const stem = basename(file, ".rs");
			args = ["test", "--manifest-path", join(PROJECT_ROOT, "Cargo.toml"),
				"--test", stem, "--", "--test-threads=1"];
		} else if (isPython) {
			cmd = "python3";
			args = ["-m", "pytest", "-v", "--tb=short", file];
		} else {
			// Node test runner for JS/TS
			cmd = process.execPath;
			args = ["--test", "--test-concurrency=1", "--test-reporter=tap",
				"--test-force-exit", `--test-timeout=${PER_FILE_TIMEOUT_MS}`, file];
		}

		// Per-file scratch space (the advertised isolation, now load-bearing):
		// the child's TMPDIR points at its own temp dir, so temp-heavy tests
		// cannot collide across pool workers. The test process itself still
		// runs with cwd=PROJECT_ROOT (pytest collection and cargo need it).
		const iso = mkdtempSync(join(tmpdir(), "dg-test-iso-"));
		const env = { ...process.env, TMPDIR: iso };
		const child = spawn(cmd, args, { cwd: PROJECT_ROOT, env });
		child.on("close", () => {
			setTimeout(() => { try { rmSync(iso, { recursive: true, force: true }); } catch { /* best-effort */ } }, 500);
		});

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
	// Discover test files ANYWHERE in the project (the documented contract —
	// README/AGENTS promise tests "found anywhere in your project"). The old
	// four-directory allowlist (dist/test/tests/src) silently never ran tests
	// living under pkg/, scripts/, or the repo root. SKIP_DIRS keeps vendored
	// and generated trees out; .devgate/ is skipped so the framework's own
	// gates don't double-run in a submodule layout (in a standalone checkout
	// the repo's own tests ARE the project's tests and are discovered).
	const all = collectTestFiles(PROJECT_ROOT);

	// Deduplicate
	const seen = new Set();
	const unique = all.filter(f => { if (seen.has(f)) return false; seen.add(f); return true; });

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
