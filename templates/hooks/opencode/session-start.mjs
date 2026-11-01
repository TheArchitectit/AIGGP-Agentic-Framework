#!/usr/bin/env node
/**
 * OpenCode session-start adapter for `aiggp.session/v1`.
 *
 * Thin 3-step adapter:
 *   1. Build the `aiggp.session/v1` (`kind: "work"`) manifest from OpenCode's
 *      session event / environment.
 *   2. Invoke `python3 <devgate>/scripts/game_session_start.py --stdin --root <root>`.
 *   3. Exit 0 -> print/return the advisory block; exit 2 or 1 -> refuse with
 *      the brain's exit code and stderr.
 */
// spec: session-01, session-02, session-03, session-04, session-06

import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { basename, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export function resolveBrainScript(projectRoot) {
  const sub = resolve(projectRoot, ".devgate", "scripts", "game_session_start.py");
  if (existsSync(sub)) return sub;
  const direct = resolve(projectRoot, "scripts", "game_session_start.py");
  if (existsSync(direct)) return direct;
  return sub;
}

export function buildOpenCodeManifest(projectRoot, event = {}) {
  const game =
    event.game ||
    process.env.AIGGP_GAME ||
    basename(resolve(projectRoot)).toLowerCase().replace(/\s+/g, "-");
  const openedAt =
    event.opened_at ||
    process.env.AIGGP_OPENED_AT ||
    new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const agent = { carrier: "opencode" };
  const sid = event.session_id || process.env.OPENCODE_SESSION_ID;
  if (typeof sid === "string" && sid.trim()) agent.session_id = sid.trim();

  const doc = {
    schema: "aiggp.session/v1",
    kind: event.kind || process.env.AIGGP_SESSION_KIND || "work",
    game: String(game),
    opened_at: String(openedAt),
    opened_by: "agent:opencode",
    agent,
  };
  const phase = event.phase || process.env.AIGGP_PHASE;
  if (typeof phase === "string" && phase.trim()) doc.phase = phase.trim();
  const seed = event.seed ?? process.env.AIGGP_SEED;
  if (seed !== undefined) doc.seed = String(seed);
  const scopeRaw = process.env.AIGGP_SCOPE || "";
  if (scopeRaw.trim()) {
    doc.scope = scopeRaw.split(",").map((s) => s.trim()).filter(Boolean);
  } else if (Array.isArray(event.scope) && event.scope.length > 0) {
    doc.scope = event.scope.map(String);
  }
  const stream = process.env.AIGGP_STREAM_ID || event.capture?.stream_id;
  if (typeof stream === "string" && stream.trim()) {
    doc.capture = {
      stream_id: stream.trim(),
      review: Boolean(event.capture?.review || process.env.AIGGP_CAPTURE_REVIEW === "1"),
    };
  }
  return doc;
}

export function runOpenCodeSessionStart(options = {}) {
  const root = resolve(options.projectRoot || process.env.AIGGP_PROJECT_ROOT || process.cwd());
  const brain = resolveBrainScript(root);
  if (!existsSync(brain)) {
    const msg = `game-session-start: cannot say - scripts/game_session_start.py not found under ${root}`;
    return { exitCode: 1, stdout: "", stderr: msg };
  }
  const manifest = buildOpenCodeManifest(root, options.event || {});
  const res = spawnSync("python3", [brain, "--stdin", "--root", root], {
    input: JSON.stringify(manifest),
    encoding: "utf-8",
  });
  return {
    exitCode: res.status ?? 1,
    stdout: res.stdout || "",
    stderr: res.stderr || "",
  };
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  let ev = {};
  if (!process.stdin.isTTY) {
    try {
      const raw = readFileSync(0, "utf-8").trim();
      if (raw) ev = JSON.parse(raw);
    } catch {
      ev = {};
    }
  }
  const out = runOpenCodeSessionStart({ event: ev });
  if (out.stdout) process.stdout.write(out.stdout);
  if (out.stderr) process.stderr.write(out.stderr);
  process.exit(out.exitCode);
}
