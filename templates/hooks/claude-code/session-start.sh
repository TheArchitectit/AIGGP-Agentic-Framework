#!/usr/bin/env bash
# spec: session-01, session-02, session-03, session-04, session-06
# Claude Code SessionStart adapter for aiggp.session/v1.
# Thin 3-step adapter: (1) build manifest JSON, (2) call game_session_start.py
# --stdin, (3) emit stdout on exit 0 or refuse with non-zero exit.
set -uo pipefail

ROOT="${AIGGP_PROJECT_ROOT:-$(pwd)}"
if [ -f "$ROOT/.devgate/scripts/game_session_start.py" ]; then
  BRAIN="$ROOT/.devgate/scripts/game_session_start.py"
elif [ -f "$ROOT/scripts/game_session_start.py" ]; then
  BRAIN="$ROOT/scripts/game_session_start.py"
else
  echo "game-session-start: cannot say - scripts/game_session_start.py not found under $ROOT" >&2
  exit 1
fi

EVENT_JSON=""
if [ ! -t 0 ]; then
  EVENT_JSON="$(cat)"
fi

MANIFEST="$(EVENT_JSON="$EVENT_JSON" ROOT="$ROOT" python3 -c '
import datetime, json, os, pathlib
root = pathlib.Path(os.environ["ROOT"]).resolve()
raw = os.environ.get("EVENT_JSON", "").strip()
ev = {}
if raw:
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            ev = parsed
    except Exception:
        ev = {}
game = os.environ.get("AIGGP_GAME") or ev.get("game") or root.name.lower().replace(" ", "-")
opened_at = os.environ.get("AIGGP_OPENED_AT") or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
agent = {"carrier": "claude-code"}
sid = os.environ.get("CLAUDE_SESSION_ID") or ev.get("session_id")
if isinstance(sid, str) and sid.strip():
    agent["session_id"] = sid.strip()
doc = {
    "schema": "aiggp.session/v1",
    "kind": os.environ.get("AIGGP_SESSION_KIND", "work"),
    "game": str(game),
    "opened_at": str(opened_at),
    "opened_by": "agent:claude-code",
    "agent": agent,
}
phase = os.environ.get("AIGGP_PHASE") or ev.get("phase")
if isinstance(phase, str) and phase.strip():
    doc["phase"] = phase.strip()
seed = os.environ.get("AIGGP_SEED") or ev.get("seed")
if seed is not None:
    doc["seed"] = str(seed)
scope_raw = os.environ.get("AIGGP_SCOPE", "").strip()
if scope_raw:
    doc["scope"] = [s.strip() for s in scope_raw.split(",") if s.strip()]
elif isinstance(ev.get("scope"), list) and ev["scope"]:
    doc["scope"] = [str(s) for s in ev["scope"]]
stream = os.environ.get("AIGGP_STREAM_ID", "").strip()
if stream:
    doc["capture"] = {"stream_id": stream, "review": os.environ.get("AIGGP_CAPTURE_REVIEW") == "1"}
print(json.dumps(doc))
')"

printf '%s\n' "$MANIFEST" | python3 "$BRAIN" --stdin --root "$ROOT"
exit $?
