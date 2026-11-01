/**
 * pi-extension session-init adapter for `aiggp.session/v1`.
 *
 * Thin 3-step adapter:
 *   1. Build the `aiggp.session/v1` (`kind: "work"`) manifest from the Pi host event.
 *   2. Invoke `python3 <devgate>/scripts/game_session_start.py --stdin --root <root>`.
 *   3. Exit 0 -> inject the advisory block into the Pi session context;
 *      exit 2 or 1 -> record a critical halt on `SessionStore` and throw to block.
 *
 * Business logic in an adapter is a defect — schema validation, determinism
 * policy, registry filtering, and `.guardrails/sessions.jsonl` writes belong
 * exclusively to `scripts/game_session_start.py`.
 */
// spec: session-01, session-02, session-03, session-04, session-06

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { basename, resolve } from "node:path";

export interface PiSessionStoreLike {
  recordHalt(reason: string, severity: "warning" | "critical"): void;
}

export interface PiHostDeps {
  projectRoot?: string;
  sessionStore?: PiSessionStoreLike;
  injectAdvisory?: (advisoryText: string) => void;
  pythonBin?: string;
}

export interface PiSessionEvent {
  sessionId?: string;
  game?: string;
  phase?: string;
  scope?: string[];
  seed?: string;
  kind?: "work" | "play";
  openedAt?: string;
  capture?: { stream_id: string; review?: boolean };
}

export interface PiSessionInitResult {
  exitCode: number;
  advisory: string;
  stderr: string;
}

export function resolveBrainScript(projectRoot: string): string {
  const sub = resolve(projectRoot, ".devgate", "scripts", "game_session_start.py");
  if (existsSync(sub)) return sub;
  const direct = resolve(projectRoot, "scripts", "game_session_start.py");
  if (existsSync(direct)) return direct;
  return sub;
}

export function buildPiSessionManifest(
  projectRoot: string,
  event: PiSessionEvent = {},
): Record<string, unknown> {
  const game =
    event.game ||
    process.env.AIGGP_GAME ||
    basename(resolve(projectRoot)).toLowerCase().replace(/\s+/g, "-");
  const openedAt =
    event.openedAt ||
    process.env.AIGGP_OPENED_AT ||
    new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const agent: Record<string, string> = { carrier: "pi-extension" };
  const sid = event.sessionId || process.env.PI_SESSION_ID;
  if (sid && sid.trim()) agent.session_id = sid.trim();

  const manifest: Record<string, unknown> = {
    schema: "aiggp.session/v1",
    kind: event.kind || (process.env.AIGGP_SESSION_KIND as "work" | "play") || "work",
    game,
    opened_at: openedAt,
    opened_by: "agent:pi-extension",
    agent,
  };
  const phase = event.phase || process.env.AIGGP_PHASE;
  if (phase && phase.trim()) manifest.phase = phase.trim();
  if (event.scope && event.scope.length > 0) manifest.scope = event.scope;
  const seed = event.seed ?? process.env.AIGGP_SEED;
  if (seed !== undefined) manifest.seed = seed;
  if (event.capture) manifest.capture = event.capture;
  return manifest;
}

export function handlePiSessionStart(
  event: PiSessionEvent = {},
  deps: PiHostDeps = {},
): PiSessionInitResult {
  const root = resolve(deps.projectRoot || process.env.AIGGP_PROJECT_ROOT || process.cwd());
  const brain = resolveBrainScript(root);
  const manifest = buildPiSessionManifest(root, event);

  const proc = spawnSync(
    deps.pythonBin || "python3",
    [brain, "--stdin", "--root", root],
    {
      input: JSON.stringify(manifest),
      encoding: "utf-8",
    },
  );

  const exitCode = proc.status ?? 1;
  const advisory = (proc.stdout || "").trimEnd();
  const stderr = (proc.stderr || "").trimEnd();

  if (exitCode !== 0) {
    const msg = stderr || `game-session-start exited with code ${exitCode}`;
    deps.sessionStore?.recordHalt(msg, "critical");
    const err = new Error(msg) as Error & { exitCode?: number };
    err.exitCode = exitCode;
    throw err;
  }

  deps.injectAdvisory?.(advisory);
  return { exitCode: 0, advisory, stderr };
}
