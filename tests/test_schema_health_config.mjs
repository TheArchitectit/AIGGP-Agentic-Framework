// Behavioral tests for schema-health-check.mjs project-overlay configuration
// (docs-and-data-truth-pass): the gate's only configuration surface is
// <project>/.guardrails/schema-health.json — consumers never edit the
// submodule. A half-configured gate (adapter without columns, or columns
// without an adapter) asserts nothing and must FAIL, not skip green.
//
// Run: node tests/test_schema_health_config.mjs
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const gate = join(repoRoot, "scripts", "schema-health-check.mjs");

let failures = 0;
function check(name, cond, detail = "") {
	if (cond) console.log(`ok - ${name}`);
	else { failures++; console.error(`FAIL - ${name}${detail ? `: ${detail}` : ""}`); }
}

function runWith(cfg) {
	const tmp = mkdtempSync(join(tmpdir(), "dg-schema-"));
	mkdirSync(join(tmp, ".guardrails"), { recursive: true });
	if (cfg !== null) {
		writeFileSync(join(tmp, ".guardrails", "schema-health.json"),
			JSON.stringify(cfg));
	}
	const r = spawnSync(process.execPath, [gate], {
		encoding: "utf-8",
		env: { ...process.env, DEVGATE_PROJECT_ROOT: tmp },
	});
	rmSync(tmp, { recursive: true, force: true });
	return r;
}

// 1. No config: explicit skip, exit 0.
let r = runWith(null);
check("no config skips green", r.status === 0, r.stdout + r.stderr);
check("skip names the config surface", /schema-health\.json/.test(r.stdout));

// 2. Adapter without columns: fail loud (would assert nothing).
r = runWith({ adapter: "sqlite", expected_columns: [] });
check("adapter without columns fails", r.status === 1, r.stdout + r.stderr);

// 3. Columns without adapter: fail loud.
r = runWith({ adapter: "none", expected_columns: [["t", "c", "T"]] });
check("columns without adapter fails", r.status === 1, r.stdout + r.stderr);

// 4. Fully configured but the engine implementation is not enabled in the
//    script: fail loud (a config naming an unavailable adapter is an error,
//    never a skip).
r = runWith({ adapter: "sqlite", expected_columns: [["t", "c", "T"]] });
check("configured adapter without implementation fails", r.status === 1,
	r.stdout + r.stderr);

// 5. Malformed config JSON: fail loud, not silently ignored.
{
	const tmp = mkdtempSync(join(tmpdir(), "dg-schema-"));
	mkdirSync(join(tmp, ".guardrails"), { recursive: true });
	writeFileSync(join(tmp, ".guardrails", "schema-health.json"), "{not json");
	const rr = spawnSync(process.execPath, [gate], {
		encoding: "utf-8",
		env: { ...process.env, DEVGATE_PROJECT_ROOT: tmp },
	});
	check("malformed config fails", rr.status === 1, rr.stdout + rr.stderr);
	rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\nALL TESTS PASSED" : `\n${failures} TEST(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
