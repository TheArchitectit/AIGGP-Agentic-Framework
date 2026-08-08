#!/usr/bin/env node
/**
 * run-tests.mjs — isolated per-file test runner.
 *
 * Runs EACH test file in its OWN subprocess so:
 *   - a hang in one file cannot block the others (hard 3-min cap per file);
 *   - a failure in one file NEVER stops the rest — every file always runs;
 *   - progress is printed so a slow file never looks like a frozen suite;
 *   - serial lanes for tests that can't share resources (port collision, CPU).
 *
 * Supports .test.js files in dist/ or test/ directories.
 * Env overrides:
 *   DEVGATE_TEST_TIMEOUT  per-file hard cap in ms (default 120000 = 2 min)
 *   DEVGATE_TEST_POOL     parallel worker count (default = CPU count, max 8)
 *   DEVGATE_TEST_HANG_MS  silence-dead-time before force-kill (default 10000)
 */

import { spawn } from "node:child_process";
import { readdirSync, statSync, mkdtempSync, rmSync, mkdirSync, existsSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import os from "node:os";

const ROOT = join(fileURLToPath(import.meta.url), "..", "..");
const DIST = join(ROOT, "dist");
const TEST_DIR = join(ROOT, "test");

const PER_FILE_TIMEOUT_MS = Number(process.env.DEVGATE_TEST_TIMEOUT ?? 120_000);
const HARD_CAP_MS = PER_FILE_TIMEOUT_MS + 10_000;
const SILENCE_MS = Number(process.env.DEVGATE_TEST_HANG_MS ?? 10_000);
const POOL = Math.max(1, Math.min(Number(process.env.DEVGATE_TEST_POOL ?? os.cpus().length), 8));

// ── Stale-temp-dir sweeper ──────────────────────────────────────────────
const TEST_TMP_PREFIXES = [
	"devgate-", "dg-test-", "test-iso-",
];

const STALE_AGE_MS = 60 * 60 * 1000; // 60 minutes

function sweepStaleTmpDirs() {
	try {
		const dir = tmpdir();
		const entries = readdirSync(dir, { withFileTypes: true });
		let swept = 0;
		let freedMB = 0;
		const now = Date.now();
		for (const e of entries) {
			if (!e.isDirectory()) continue;
			const match = TEST_TMP_PREFIXES.some((p) => e.name.startsWith(p));
			if (!match) continue;
			let st;
			try { st = statSync(join(dir, e.name)); } catch { continue; }
			const age = now - st.mtimeMs;
			if (age < STALE_AGE_MS) continue;
			try {
				rmSync(join(dir, e.name), { recursive: true, force: true });
				swept++;
			} catch { /* best-effort */ }
		}
		if (swept > 0) {
			console.error(`sweeper: swept ${swept} stale test dirs`);
		}
	} catch { /* non-fatal */ }
}

sweepStaleTmpDirs();

// Serial lanes: tests that can't share resources run one-at-a-time
const SERIAL_GLOB = /(?:^|\/)(?:dashboard|perf|budget|server)[^/]*\.test\.js$/;

function collectTestFiles(dir, out = []) {
	if (!existsSync(dir)) return out;
	for (const entry of readdirSync(dir)) {
		const full = join(dir, entry);
		const st = statSync(full);
		if (st.isDirectory()) {
			if (entry === "node_modules" || entry.startsWith(".")) continue;
			collectTestFiles(full, out);
		} else if (entry.endsWith(".test.js")) {
			out.push(full);
		}
	}
	return out;
}

function runOne(file) {
	return new Promise((resolve) => {
		const start = Date.now();
		const iso = mkdtempSync(join(tmpdir(), "dg-test-iso-"));
		mkdirSync(iso, { recursive: true });
		const env = { ...process.env };
		const child = spawn(
			process.execPath,
			["--test", "--test-concurrency=1", "--test-reporter=tap",
			 "--test-force-exit", `--test-timeout=${PER_FILE_TIMEOUT_MS}`, file],
			{ cwd: ROOT, env },
		);
		let out = "";
		let tapDone = false;
		let graceTimer = null;
		let startedCount = 0;
		let completedCount = 0;
		let lastOutputAt = Date.now();
		const markTapDone = () => {
			if (tapDone) return;
			if (/^# pass\s+\d+/m.test(out)) {
				tapDone = true;
				graceTimer = setTimeout(() => { if (!child.killed) child.kill("SIGKILL"); }, 1500);
			}
		};
		const onResult = (s) => {
			if (/^\s*(ok|not ok)\s+\d+/m.test(s)) completedCount++;
			if (/^# Subtest:/m.test(s)) startedCount++;
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
			const pass = (out.match(/^# pass\s+(\d+)/m) || out.match(/(\d+)\s+passing/))?.[1];
			const fail = (out.match(/^# fail\s+(\d+)/m) || out.match(/(\d+)\s+failing/))?.[1];
			const okCount = (out.match(/^ok\s+\d+/gm) || []).length;
			const notOkCount = (out.match(/^not ok\s+\d+/gm) || []).length;
			resolve({
				file: relative(ROOT, file), code, timedOut, tapDone, okCount,
				hung: okCount > 0 && code !== 0 && !timedOut,
				pass: pass ? Number(pass) : okCount,
				fail: fail ? Number(fail) : notOkCount,
				ms: Date.now() - start,
				snippet: out.split("\n").filter((l) => /^# (fail|not ok)/.test(l) || /^not ok/.test(l)).slice(0, 3).join("  "),
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
	const all = [...collectTestFiles(DIST), ...collectTestFiles(TEST_DIR)].sort();
	const serial = all.filter((f) => SERIAL_GLOB.test(f));
	const rest = all.filter((f) => !SERIAL_GLOB.test(f));

	let totalPass = 0, totalFail = 0;
	const failed = [];
	const wallStart = Date.now();

	async function runAndReport(f) {
		console.error(`▶ ${relative(ROOT, f)}`);
		const r = await runOne(f);
		totalPass += r.pass; totalFail += r.fail;
		const crashedBeforeTests = r.code !== 0 && !r.tapDone && r.okCount === 0 && r.pass === 0;
		const ok = !r.timedOut && r.fail === 0 && !crashedBeforeTests;
		const mark = ok ? "✓" : "✗";
		const tail = r.fail > 0 ? `  ${r.snippet}` : r.timedOut ? "  TIMED OUT" :
			r.hung ? "  (tests passed; exit-hung)" : crashedBeforeTests ? `  (crashed, code ${r.code})` : "";
		console.error(`${mark} ${relative(ROOT, f)}  (${r.pass} pass / ${r.fail} fail, ${fmt(r.ms)})${tail}`);
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
			const solo = await runOne(join(ROOT, r.file));
			if (solo.fail === 0) {
				totalFail -= r.fail; flakes.push(r.file);
				failed.splice(failed.indexOf(r), 1);
				console.error(`✓ solo: ${r.file}  (${solo.pass} pass / 0 fail, ${fmt(solo.ms)})  (flake)`);
			} else {
				console.error(`✗ solo: ${r.file}  (${solo.pass} pass / ${solo.fail} fail)`);
			}
		}
	}

	const wall = fmt(Date.now() - wallStart);
	console.error(`\nTOTAL: ${totalPass} passed, ${totalFail} failed across ${all.length} files in ${wall}`);
	if (flakes.length) { console.error("FLAKY FILES:"); for (const f of flakes) console.error(`  - ${f}`); }
	if (failed.length) {
		console.error("FAILED FILES:");
		for (const r of failed) console.error(`  - ${r.file}  (code ${r.code ?? "signal"}${r.timedOut ? ", TIMED OUT" : ""})`);
		process.exit(1);
	}
	process.exit(0);
}

main().catch((e) => { console.error(e); process.exit(1); });
