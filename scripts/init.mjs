#!/usr/bin/env node
/**
 * init.mjs — DevGate quickstart (R16): take a consumer repo from zero to a
 * green baseline run.
 *
 * Idempotent and fail-closed:
 *   - adds DevGate as the .devgate submodule (skips if present)
 *   - copies the 3 baseline workflows, resolving CUSTOMIZE placeholders
 *     (interactive prompt, or --cron/--labels flags for non-interactive use)
 *   - writes a project .guardrails/ overlay skeleton — REFUSES to overwrite
 *     an existing overlay
 *   - prints the 4 gate commands
 *
 * --dry-run: print what would happen, change nothing.
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createInterface } from "node:readline";

const DEVGATE_ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const TARGET = resolve(process.argv[2] && !process.argv[2].startsWith("--")
  ? process.argv[2] : ".");
const DRY = process.argv.includes("--dry-run");
const flag = (name) => {
  const i = process.argv.indexOf(`--${name}`);
  return i === -1 ? null : process.argv[i + 1] ?? null;
};
const cron = flag("cron") ?? null;
const labels = flag("labels") ?? null;

const WORKFLOWS = ["guardrails-compliance.yml", "secret-validation.yml",
  "drift-scan.yml"];
const GATES = [
  "node .devgate/scripts/guardrails-scan.mjs",
  "node .devgate/scripts/semantic-scan.mjs",
  "python3 .devgate/scripts/regression_check.py --all --fail-if-empty",
  "bash .devgate/scripts/silent-success-scan.sh",
];

function fail(msg) {
  console.error(`init: FAIL — ${msg}`);
  process.exit(1);
}
function note(msg) { console.log(`init: ${msg}`); }

// 1. Submodule (skip when already present)
const dgDir = join(TARGET, ".devgate");
if (existsSync(dgDir)) {
  note(`.devgate exists — skipping submodule add`);
} else if (DRY) {
  note(`[dry-run] would add submodule: git submodule add ${DEVGATE_ROOT} .devgate`);
} else {
  const { execFileSync } = await import("node:child_process");
  try {
    execFileSync("git", ["submodule", "add", DEVGATE_ROOT, ".devgate"],
      { cwd: TARGET, stdio: "inherit" });
    execFileSync("git", ["submodule", "update", "--init", "--recursive"],
      { cwd: TARGET, stdio: "inherit" });
  } catch (e) {
    fail(`submodule add failed: ${e.message}`);
  }
}

// 2. Overlay skeleton — refuse to overwrite
const overlay = join(TARGET, ".guardrails", "prevention-rules");
if (existsSync(overlay)) {
  note(`.guardrails/ overlay exists — left untouched`);
} else if (DRY) {
  note(`[dry-run] would write overlay skeleton at .guardrails/prevention-rules/`);
} else {
  mkdirSync(overlay, { recursive: true });
  writeFileSync(join(TARGET, ".guardrails", "scope.json"),
    readFileSync(join(DEVGATE_ROOT, ".guardrails", "scope.json")));
  writeFileSync(join(TARGET, ".guardrails", "prevention-rules",
    "README.md"),
    "# Project overlay\n\nExtend the baseline via gate_overlay conventions:\n"
    + "new rule ids append, same-id entries replace. See AGENTS.md.\n");
  note(`overlay skeleton written (.guardrails/)`);
}

// 3. Baseline workflows with CUSTOMIZE resolution
const wfDir = join(TARGET, ".github", "workflows");
let answers = { cron, labels };
if ((!answers.cron || !answers.labels) && !DRY && process.stdin.isTTY) {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const q = (p) => new Promise((r) => rl.question(p, r));
  answers.cron ??= await q("Drift-scan cron (UTC, avoid :00/:30) [23 4 * * *]: ");
  answers.labels ??= await q("Self-hosted runner label(s), comma-separated [ubuntu-latest]: ");
  rl.close();
}
answers.cron ??= "23 4 * * *";
answers.labels ??= "ubuntu-latest";

if (DRY) {
  note(`[dry-run] would write ${WORKFLOWS.join(", ")} with cron=${answers.cron}`);
} else {
  mkdirSync(wfDir, { recursive: true });
  for (const name of WORKFLOWS) {
    const src = join(DEVGATE_ROOT, "templates", "github-workflows", name);
    if (!existsSync(src)) fail(`template missing: ${name}`);
    let text = readFileSync(src, "utf8")
      .replaceAll("CUSTOMIZE: nightly full-tree sweep. Avoid :00/:30 (shared CI crunch).", "")
      .replace(/- cron: '[^']*'/, `- cron: '${answers.cron}'`)
      .replace(/runs-on: ubuntu-latest/g, `runs-on: ${answers.labels.split(",")[0].trim()}`);
    writeFileSync(join(wfDir, name), text);
    note(`workflow written: .github/workflows/${name}`);
  }
}

// 4. The four gates + honest next step
console.log("\nBaseline gates (run from the project root):");
for (const g of GATES) console.log(`  ${g}`);
console.log("\nIf a gate is red: that is the point. Fix, or allowlist with a");
console.log("reason in .guardrails/ (never blanket-suppress). False positive?");
console.log("Use .github/ISSUE_TEMPLATE/false-positive-report.md.");
if (DRY) console.log("\n[dry-run] nothing was written.");
