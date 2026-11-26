// Executable pi-extension carrier fixture. The Python test supplies the repo
// root and the pinned tsx runner; both the accept and refusal paths are real.
import { cpSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { handlePiSessionStart } from "../../templates/hooks/pi-extension/session-init.ts";

const repo = process.env.AIGGP_REPO_ROOT;
if (!repo) throw new Error("AIGGP_REPO_ROOT is required");
const root = mkdtempSync(join(tmpdir(), "pi-session-carrier-"));
mkdirSync(join(root, ".devgate", "scripts", "lib"), { recursive: true });
mkdirSync(join(root, ".devgate", ".guardrails", "prevention-rules"), { recursive: true });
for (const file of ["game_session_start.py", "gate_common.py", "gate_overlay.py"]) {
  cpSync(join(repo, "scripts", file), join(root, ".devgate", "scripts", file));
}
cpSync(join(repo, "scripts", "lib"), join(root, ".devgate", "scripts", "lib"), { recursive: true });
cpSync(
  join(repo, ".guardrails", "prevention-rules", "session-manifest.schema.json"),
  join(root, ".devgate", ".guardrails", "prevention-rules", "session-manifest.schema.json"),
);
writeFileSync(
  join(root, "game-manifest.json"),
  JSON.stringify({ engine: "Godot", determinism: { enabled: true } }),
);

let injected = "";
const accepted = handlePiSessionStart(
  { game: "mergekingdom", phase: "alpha", sessionId: "pi-accept" },
  { projectRoot: root, injectAdvisory: (text) => { injected = text; } },
);
if (accepted.exitCode !== 0 || !injected.includes("work session in mergekingdom")) {
  throw new Error("accepted session did not inject the advisory");
}

let refusedExit = -1;
let halt = "";
try {
  handlePiSessionStart(
    { game: "mergekingdom", kind: "play", sessionId: "pi-refuse" },
    {
      projectRoot: root,
      sessionStore: { recordHalt: (_reason, severity) => { halt = severity; } },
    },
  );
} catch (err) {
  refusedExit = (err as Error & { exitCode?: number }).exitCode ?? -1;
}
if (refusedExit !== 2 || halt !== "critical") {
  throw new Error(`refusal was not critical/2: ${refusedExit} ${halt}`);
}
const rows = readFileSync(join(root, ".guardrails", "sessions.jsonl"), "utf8").trim().split("\n");
if (rows.length !== 1) throw new Error("refused session was appended");
console.log("pi-extension: accept/inject and critical refusal verified");
