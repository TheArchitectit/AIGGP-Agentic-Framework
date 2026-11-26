import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

const workflow = readFileSync(new URL("../.github/workflows/ci.yml", import.meta.url), "utf8");

function shellStep(id) {
	const lines = workflow.split(/\r?\n/);
	const step = lines.indexOf(`        id: ${id}`);
	assert.ok(step >= 0, `missing workflow step ${id}`);
	const run = lines.indexOf("        run: |", step);
	assert.ok(run > step, `missing shell commands for ${id}`);
	const block = [];
	for (let i = run + 1; i < lines.length && lines[i].startsWith("          "); i++) {
		block.push(lines[i].slice(10));
	}
	assert.ok(block.length > 0);
	return block.join("\n");
}

const noBash = spawnSync("bash", ["--version"], { encoding: "utf8" }).status !== 0;

function runShell(commands, root, env) {
	return spawnSync("bash", ["-e", "-o", "pipefail", "-c", commands], {
		cwd: root,
		env: { ...process.env, ...env },
		encoding: "utf8",
	});
}

function checkedRunner(t, reportLine, exitCode) {
	const root = mkdtempSync(join(tmpdir(), "devgate-runner-report-"));
	t.after(() => rmSync(root, { recursive: true, force: true }));
	mkdirSync(join(root, "scripts"));
	const calls = join(root, "calls.txt");
	const output = join(root, "step-output.txt");
	writeFileSync(join(root, "scripts", "run-tests.mjs"), `
		import { appendFileSync } from "node:fs";
		appendFileSync(${JSON.stringify(calls)}, "called\\n");
		console.error(${JSON.stringify(reportLine)});
		process.exit(${exitCode});
	`);

	const first = runShell(shellStep("per_file_runner"), root, {
		RUNNER_TEMP: root,
		GITHUB_OUTPUT: output,
	});
	const report = existsSync(output) ? readFileSync(output, "utf8").trim().slice("report_path=".length) : "";
	const assertOnce = () => assert.equal(readFileSync(calls, "utf8"), "called\n");
	return {
		first,
		report,
		assertOnce,
		check: (path = report) => runShell(shellStep("runner_non_vacuity"), root, { RUNNER_REPORT: path }),
	};
}

test("the CI report step accepts the successful runner's original output", { skip: noBash }, (t) => {
	const runner = checkedRunner(t, "TOTAL: 4 passed, 0 failed across 2 files in 1s", 0);
	assert.equal(runner.first.status, 0, runner.first.stderr);
	assert.ok(runner.report && existsSync(runner.report));
	const second = runner.check();
	assert.equal(second.status, 0, second.stderr);
	assert.match(second.stdout, /discovered 2 test file/);
	runner.assertOnce();
});

test("the CI report step rejects missing, malformed, and zero file counts", { skip: noBash }, (t) => {
	for (const report of ["unexpected report", "TOTAL: 0 passed, 0 failed across 0 files in 1s"]) {
		const runner = checkedRunner(t, report, 0);
		assert.equal(runner.first.status, 0);
		assert.equal(runner.check().status, 1);
		assert.equal(runner.check("").status, 1);
		assert.equal(runner.check(join(tmpdir(), "devgate-report-does-not-exist-1234")).status, 1);
		runner.assertOnce();
	}
});

test("the failing runner cannot publish a report even with a positive count", { skip: noBash }, (t) => {
	const runner = checkedRunner(t, "TOTAL: 1 passed, 0 failed across 1 files in 1s", 7);
	assert.equal(runner.first.status, 7);
	assert.equal(runner.report, "");
	assert.equal(runner.check().status, 1);
	runner.assertOnce();
});
