// Behavioral tests for bundle-size-check.mjs (bundle-size-gate): the gate's
// only configuration surface is <project>/.guardrails/bundle-size.json -
// consumers never edit the submodule. The honesty contract under test:
// a skip (no config) is exit 2 and never 0, and a configured run with
// nothing measurable (missing or empty dist) FAILS rather than passing
// vacuously.
//
// Run: node tests/test_bundle_size_check.mjs
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const gate = join(repoRoot, "scripts", "bundle-size-check.mjs");

let failures = 0;
function check(name, cond, detail = "") {
	if (cond) console.log(`ok - ${name}`);
	else { failures++; console.error(`FAIL - ${name}${detail ? `: ${detail}` : ""}`); }
}

function runWith(cfg, makeDist) {
	const tmp = mkdtempSync(join(tmpdir(), "dg-bundle-"));
	mkdirSync(join(tmp, ".guardrails"), { recursive: true });
	if (cfg !== null) {
		writeFileSync(join(tmp, ".guardrails", "bundle-size.json"),
			typeof cfg === "string" ? cfg : JSON.stringify(cfg));
	}
	if (makeDist) makeDist(tmp);
	const r = spawnSync(process.execPath, [gate], {
		encoding: "utf-8",
		env: { ...process.env, DEVGATE_PROJECT_ROOT: tmp },
	});
	rmSync(tmp, { recursive: true, force: true });
	return r;
}

function withAsset(bytes) {
	return (tmp) => {
		mkdirSync(join(tmp, "dist", "assets"), { recursive: true });
		// Fixed size: a file of N 0-bytes measures N bytes exactly.
		writeFileSync(join(tmp, "dist", "assets", "index.js"), Buffer.alloc(bytes));
	};
}

// 1. No config: explicit skip. Exit 2, never 0 - a skip and a pass must not
//    share an exit code ("skip is green" is the silent-success shape this
//    gate exists to refuse).
let r = runWith(null, null);
check("no config is a loud skip", r.status === 2, r.stdout + r.stderr);
check("skip names the config surface", /bundle-size\.json/.test(r.stdout));

// 2. Positive control: an asset under the budget passes (exit 0).
r = runWith({ max_kb: 10 }, withAsset(2048));
check("under-limit asset passes", r.status === 0, r.stdout + r.stderr);

// 3. Over budget: fail loud and name the offending file.
r = runWith({ max_kb: 1 }, withAsset(4096));
check("over-limit asset fails", r.status === 1, r.stdout + r.stderr);
check("violation names the file", /index\.js/.test(r.stdout + r.stderr));

// 3b. The budget is KiB (bytes/1024), the vite chunkSizeWarningLimit unit:
//     1500 bytes is 1.46 KiB and must exceed max_kb 1, while 1000 bytes
//     (0.98 KiB) must not.
r = runWith({ max_kb: 1 }, withAsset(1500));
check("bytes/1024 comparison (over)", r.status === 1, r.stdout + r.stderr);
r = runWith({ max_kb: 1 }, withAsset(1000));
check("bytes/1024 comparison (under)", r.status === 0, r.stdout + r.stderr);

// 4. Configured but no dist at all: fail loud (a missing build is not a
//    pass - the consumer asked for the check and got no input).
r = runWith({ max_kb: 10 }, null);
check("missing dist fails", r.status === 1, r.stdout + r.stderr);

// 5. Dist exists but matches nothing measurable: fail loud (vacuous input).
r = runWith({ max_kb: 10 }, (tmp) => {
	mkdirSync(join(tmp, "dist"), { recursive: true });
	writeFileSync(join(tmp, "dist", "index.html"), "<html></html>");
});
check("empty dist fails closed", r.status === 1, r.stdout + r.stderr);

// 6. Malformed config JSON: fail loud, not silently ignored.
r = runWith("{not json", withAsset(100));
check("malformed config fails", r.status === 1, r.stdout + r.stderr);

// 7. Present-but-unusable values fail; defaults only fill absent keys.
r = runWith({ max_kb: 0 }, withAsset(100));
check("max_kb of 0 fails", r.status === 1, r.stdout + r.stderr);
r = runWith({ max_kb: "900" }, withAsset(100));
check("max_kb as a string fails", r.status === 1, r.stdout + r.stderr);
r = runWith({ include: [] }, withAsset(100));
check("empty include fails", r.status === 1, r.stdout + r.stderr);

// 8. include patterns scope the walk: a non-matching asset is not measured,
//    and a build whose only assets are out of scope is vacuous (fail).
r = runWith({ max_kb: 1, include: ["**/*.css"] }, withAsset(4096));
check("non-matching assets are vacuous input", r.status === 1, r.stdout + r.stderr);

console.log(failures === 0 ? "\nALL TESTS PASSED" : `\n${failures} TEST(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
