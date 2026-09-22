#!/usr/bin/env bash
# runner-heartbeat.sh — post ONE heartbeat for the runner named by its env.
#
# runner-enroll.sh copies this to ~/.config/containers/devgate-heartbeat.sh
# and points ExecStart at that path. It is never inlined into a unit: systemd
# performs $ expansion on ExecStart, so an inline `bash -c '…$RUNNER_NAME…'`
# has every variable mangled before bash sees it, the post goes out malformed,
# the hub answers non-200, and the unit exits 22 on every single tick.
#
# Required env (supplied by the unit's per-runner EnvironmentFile):
#   HUB_URL, RUNNER_NAME, HEARTBEAT_TOKEN
#
# Exit codes:
#   0   hub accepted the heartbeat (HTTP 200)
#   1   required env missing — the unit's EnvironmentFile was not read
#   22  hub answered with a non-200
#   *   curl's own code when the hub could not be reached (still a failure —
#       a heartbeat that did not happen must never look like a pass)

set -euo pipefail

: "${HUB_URL:?HUB_URL is not set - check the unit EnvironmentFile}"
: "${RUNNER_NAME:?RUNNER_NAME is not set - check the unit EnvironmentFile}"
: "${HEARTBEAT_TOKEN:?HEARTBEAT_TOKEN is not set - check the unit EnvironmentFile}"

disk_pct="$(df --output=pcent / | tail -1 | tr -d ' %')"
disk_ok=false
if [ "$disk_pct" -lt 90 ]; then disk_ok=true; fi

podman_ok=false
if command -v podman >/dev/null 2>&1 \
    && podman info --format '{{.Host.Security.Rootless}}' >/dev/null 2>&1; then
    podman_ok=true
fi

body="$(python3 -c 'import json, os, sys
print(json.dumps({
    "runner_name": os.environ["RUNNER_NAME"],
    "heartbeat_token": os.environ["HEARTBEAT_TOKEN"],
    "disk_ok": sys.argv[1] == "true",
    "podman_ok": sys.argv[2] == "true",
}))' "$disk_ok" "$podman_ok")"

# The response is kept for diagnosis, so its filename must be filesystem-safe.
# A name containing "/" makes curl unable to open the -o target (exit 23), and
# set -e turns that into a dead tick before the HTTP status is even checked.
safe_name="$(printf '%s' "$RUNNER_NAME" | LC_ALL=C sed 's/[^A-Za-z0-9_-]/-/g')"
resp="${TMPDIR:-/tmp}/devgate-hb-last-resp-${safe_name}.json"
code="$(curl -sS -o "$resp" -w '%{http_code}' -X POST \
    -H 'Content-Type: application/json' \
    -d "$body" \
    "$HUB_URL/heartbeat")"

echo "[hb:$RUNNER_NAME] HTTP $code"
if [ "$code" != "200" ]; then
    echo "[hb:$RUNNER_NAME] hub response: $(cat "$resp" 2>/dev/null || true)" >&2
    exit 22
fi
