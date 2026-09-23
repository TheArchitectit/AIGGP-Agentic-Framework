#!/usr/bin/env bash
# hub-watchdog.sh — a spoke-side liveness check on the monitor hub.
#
# The inverted dead-man switch. A GitHub-scheduled workflow cannot report its
# own absence, and the hub cannot report its own death, so the check runs on
# the machines that are still alive when the hub is not: the spokes. Each
# spoke already posts heartbeats; this asks whether the hub is still *doing
# anything*, and fails its systemd unit when it is not.
#
# Local-only by design: no GitHub issue is filed and no token is needed.
# The signal is the failed `devgate-watchdog-<name>.service` unit on each
# spoke (`systemctl --user status devgate-watchdog-<name>`), for a human or an
# external monitor to pick up. See docs/runner-monitor-monitor-hub.md.
#
# Usage:
#   scripts/hub-watchdog.sh [--grace-sec N] [--timeout SEC]
#
# Reads HUB_URL from the environment — the unit points EnvironmentFile at the
# enroll script's per-runner ~/.config/containers/devgate-heartbeat-<name>.env,
# so enrollment is the only setup.
#
# Exit codes:
#   0  hub is alive (polling disabled is warned, not failed — see below)
#   1  hub unreachable, unhealthy, or its poll loop has gone stale
#   2  misconfigured (HUB_URL unset) — a check that cannot run must say so,
#      not exit 0 and look like a pass

set -euo pipefail

GRACE_SEC=""
TIMEOUT=15

while [[ $# -gt 0 ]]; do
    case "$1" in
        --grace-sec) GRACE_SEC="$2"; shift 2 ;;
        --timeout) TIMEOUT="$2"; shift 2 ;;
        -h|--help) sed -n '2,25p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "[hub-watchdog] ERROR: unknown option: $1" >&2; exit 2 ;;
    esac
done

if [[ -z "${HUB_URL:-}" ]]; then
    echo "[hub-watchdog] ERROR: HUB_URL is not set (expected from the heartbeat env file)" >&2
    exit 2
fi

HEALTH="$(curl -fsS --max-time "$TIMEOUT" "${HUB_URL%/}/health" 2>&1)" || {
    echo "[hub-watchdog] HUB UNREACHABLE at ${HUB_URL%/}/health — the hub is down or the network path is broken" >&2
    echo "[hub-watchdog] response: ${HEALTH}" >&2
    exit 1
}

# Parse with python3 (already required by runner-enroll.sh's enroll response).
# Emits "verdict reason"; verdict is ok|warn|fail.
read -r VERDICT REASON <<<"$(
    HEALTH="$HEALTH" GRACE_SEC="$GRACE_SEC" python3 - <<'PY' 2>&1 || echo "fail could_not_parse_health_json"
import json, os, sys
from datetime import datetime, timezone

try:
    h = json.loads(os.environ["HEALTH"])
except Exception:
    print("fail could_not_parse_health_json")
    sys.exit(0)

if h.get("ok") is not True:
    print("fail health_reports_not_ok")
    sys.exit(0)

def parse(ts):
    if not ts:
        return None
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

now = datetime.now(timezone.utc)
interval = int(h.get("poll_interval_sec") or 60)

# Staleness budget: a few missed cycles, never under 5 minutes. A short
# window would page on a single slow API call, not on a dead loop.
grace = int(os.environ.get("GRACE_SEC") or 0) or max(interval * 5, 300)

if not h.get("polling_enabled"):
    # The hub is alive but has no GITHUB_TOKEN, so last_poll_at is null by
    # design. We cannot judge a loop that was never started — warn, don't fail.
    print("warn polling_disabled")
    sys.exit(0)

last = parse(h.get("last_poll_at"))
uptime = float(h.get("uptime_sec") or 0)

if last is None:
    # Enabled but no cycle has completed yet. Only a failure once the hub has
    # been up long enough that one should have — a fresh hub is not a dead one.
    if uptime > grace:
        print(f"fail never_polled_after_{uptime:.0f}s")
    else:
        print("ok starting_up")
    sys.exit(0)

age = (now - last).total_seconds()
if age > grace:
    print(f"fail poll_stale_{age:.0f}s_over_{grace}s")
else:
    print(f"ok last_poll_{age:.0f}s_ago")
PY
)"

case "$VERDICT" in
    ok)
        echo "[hub-watchdog] OK: hub alive, $REASON"
        exit 0
        ;;
    warn)
        echo "[hub-watchdog] WARNING: hub alive but $REASON — API monitoring is NOT running;" >&2
        echo "[hub-watchdog] a wedged poll loop cannot be detected from this spoke until GITHUB_TOKEN is set." >&2
        exit 0
        ;;
    *)
        echo "[hub-watchdog] HUB UNHEALTHY: $REASON" >&2
        echo "[hub-watchdog] hub at ${HUB_URL%/} is not monitoring. Check the hub container" >&2
        echo "[hub-watchdog] (podman logs devgate-hub) and /health on the hub machine." >&2
        exit 1
        ;;
esac