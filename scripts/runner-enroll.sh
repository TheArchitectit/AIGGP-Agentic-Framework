#!/usr/bin/env bash
# runner-enroll.sh — enroll a DevGate self-hosted runner with the monitor hub.
#
# Usage:
#   scripts/runner-enroll.sh <hub-url> <enrollment-token> [options]
#   scripts/runner-enroll.sh --revoke <hub-url> <heartbeat-token> <runner-name>
#
# Enrolls a new runner (POST /enroll), stores the per-runner heartbeat token,
# and installs a systemd user timer (devgate-heartbeat.timer) that posts
# heartbeats to the hub every HEARTBEAT_INTERVAL_SEC (default 300s).
#
# Options:
#   --runner-name NAME    Runner name (default: hostname)
#   --repo OWNER/REPO     GitHub repo this runner serves (required for enroll)
#   --labels LABELS       Comma-separated labels (default: devgate)
#   --host-alias ALIAS    Human-readable host identifier (default: hostname)
#   --interval SEC        Heartbeat interval seconds (default: 300)
#   --revoke              Revoke mode: POST /enroll with revoke semantics
#
# Exit codes:
#   0 success
#   1 usage error
#   2 hub unreachable or enrollment failed
#   3 systemd timer installation failed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TICKET_FILE="$HOME/.devgate-heartbeat.env"
TIMER_UNIT="$HOME/.config/systemd/user/devgate-heartbeat.timer"
SERVICE_UNIT="$HOME/.config/systemd/user/devgate-heartbeat.service"
WATCHDOG_TIMER_UNIT="$HOME/.config/systemd/user/devgate-hub-watchdog.timer"
WATCHDOG_SERVICE_UNIT="$HOME/.config/systemd/user/devgate-hub-watchdog.service"

log() { echo "[runner-enroll] $*"; }
die() { log "ERROR: $*"; exit "${2:-1}"; }

usage() {
    cat <<'EOF'
Usage:
  runner-enroll.sh <hub-url> <enrollment-token> --repo OWNER/REPO [options]
  runner-enroll.sh --revoke <hub-url> <heartbeat-token> <runner-name>

Options:
  --runner-name NAME    Runner name (default: hostname)
  --repo OWNER/REPO     GitHub repo this runner serves (required for enroll)
  --labels LABELS       Comma-separated labels (default: devgate)
  --host-alias ALIAS    Human-readable host identifier (default: hostname)
  --interval SEC        Heartbeat interval seconds (default: 300)
  --revoke              Revoke this runner's heartbeat token

Examples:
  # Enroll a new runner:
  scripts/runner-enroll.sh https://monitor-hub.internal:8443 <token> \\
      --repo owner/repo --labels devgate --host-alias monitor-hub

  # Revoke (unenroll) a runner:
  scripts/runner-enroll.sh --revoke https://monitor-hub.internal:8443 <hb-token> my-runner
EOF
    exit 1
}

# --- parse args ---------------------------------------------------------------

MODE="enroll"
HUB_URL=""
ENROLL_TOKEN=""
RUNNER_NAME="$(hostname)"
REPO=""
LABELS="devgate"
HOST_ALIAS="$(hostname)"
INTERVAL=300
REVOKE_HB_TOKEN=""
REVOKE_RUNNER=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --revoke) MODE="revoke"; shift ;;
        --runner-name) RUNNER_NAME="$2"; shift 2 ;;
        --repo) REPO="$2"; shift 2 ;;
        --labels) LABELS="$2"; shift 2 ;;
        --host-alias) HOST_ALIAS="$2"; shift 2 ;;
        --interval) INTERVAL="$2"; shift 2 ;;
        -h|--help) usage ;;
        -*) die "unknown option: $1" 1 ;;
        *)
            if [[ -z "$HUB_URL" ]]; then HUB_URL="$1"
            elif [[ "$MODE" == "enroll" && -z "$ENROLL_TOKEN" ]]; then ENROLL_TOKEN="$1"
            elif [[ "$MODE" == "revoke" && -z "$REVOKE_HB_TOKEN" ]]; then REVOKE_HB_TOKEN="$1"
            elif [[ "$MODE" == "revoke" && -z "$REVOKE_RUNNER" ]]; then REVOKE_RUNNER="$1"
            else die "unexpected argument: $1" 1; fi
            shift ;;
    esac
done

# --- validate -----------------------------------------------------------------

if [[ "$MODE" == "enroll" ]]; then
    [[ -n "$HUB_URL" ]] || { usage; }
    [[ -n "$ENROLL_TOKEN" ]] || die "enrollment token required" 1
    [[ -n "$REPO" ]] || die "--repo OWNER/REPO is required for enrollment" 1
    # Identity fields are validated before they are interpolated into the
    # heartbeat unit's JSON: a quote or backslash would corrupt every
    # heartbeat payload. Labels are free-form (they go through json.dumps).
    [[ "$RUNNER_NAME" =~ ^[A-Za-z0-9._-]+$ ]] || \
        die "runner name must match [A-Za-z0-9._-]+ (got: $RUNNER_NAME)" 1
    [[ "$HOST_ALIAS" =~ ^[A-Za-z0-9._-]+$ ]] || \
        die "host alias must match [A-Za-z0-9._-]+ (got: $HOST_ALIAS)" 1
elif [[ "$MODE" == "revoke" ]]; then
    [[ -n "$HUB_URL" ]] || { usage; }
    [[ -n "$REVOKE_HB_TOKEN" ]] || die "heartbeat token required for revoke" 1
    [[ -n "$REVOKE_RUNNER" ]] || die "runner name required for revoke" 1
fi

# --- helpers ------------------------------------------------------------------

post_json() {
    local url="$1" payload="$2"
    # --max-time bounds a hung hub: without it a stuck connection wedges the
    # systemd oneshot unit indefinitely.
    curl -sf --connect-timeout 5 --max-time 15 -X POST \
        -H 'Content-Type: application/json' \
        -d "$payload" "$url" 2>&1
}

# Build the request JSON with python json.dumps — a quote, backslash, or
# newline in a label must produce a VALID payload and can never break out of
# the JSON string (the old inline string interpolation could do both).
# `labels` is comma-split into an array.
json_payload() {
    python3 - "$@" <<'PY'
import json, sys
obj = {}
for arg in sys.argv[1:]:
    key, _, value = arg.partition("=")
    if key == "labels":
        obj[key] = [v.strip() for v in value.split(",") if v.strip()]
    else:
        obj[key] = value
print(json.dumps(obj))
PY
}

# Print only non-secret fields of a hub response. The enroll response carries
# the issued heartbeat token, which must never reach stdout/CI scrollback —
# it is extracted into a variable and written straight to the 0600 env file.
response_summary() {
    python3 -c '
import json, sys
try:
    doc = json.loads(sys.stdin.read())
except Exception:
    print("(unparseable response)"); sys.exit(0)
safe = {k: v for k, v in doc.items()
        if k in ("ok", "runner_name", "error", "detail")}
print(json.dumps(safe))
'
}

install_timer() {
    local hb_token="$1"
    log "Installing systemd user timer (interval=${INTERVAL}s)..."

    mkdir -p "$(dirname "$TIMER_UNIT")"

    # Write the heartbeat env file (chmod 600 — contains the token).
    cat > "$TICKET_FILE" <<EOF
HUB_URL=$HUB_URL
RUNNER_NAME=$RUNNER_NAME
HEARTBEAT_TOKEN=$hb_token
LAST_JOB_SEEN=""
EOF
    chmod 600 "$TICKET_FILE"

    # Service unit: posts one heartbeat, exits.
    cat > "$SERVICE_UNIT" <<EOF
[Unit]
Description=DevGate runner heartbeat (one-shot)

[Service]
Type=oneshot
EnvironmentFile=$TICKET_FILE
ExecStart=/usr/bin/env bash -c '\
  DISK_OK=\$(df --output=pcent / | tail -1 | tr -d " %"); \
  [[ "\$DISK_OK" =~ ^[0-9]+$ ]] || DISK_OK=100; \
  PODMAN_OK="false"; command -v podman >/dev/null && podman info --format "{{.Host.Security.Rootless}}" >/dev/null 2>&1 && PODMAN_OK="true"; \
  curl -sf --connect-timeout 5 --max-time 15 -X POST -H "Content-Type: application/json" \
    -d "{\"runner_name\":\"\$RUNNER_NAME\",\"heartbeat_token\":\"\$HEARTBEAT_TOKEN\",\"disk_ok\":\$( [ "\$DISK_OK" -lt 90 ] && echo true || echo false ),\"podman_ok\":\$PODMAN_OK}" \
    "\$HUB_URL/heartbeat"'
EOF

    # Timer unit: fires every INTERVAL seconds.
    cat > "$TIMER_UNIT" <<EOF
[Unit]
Description=DevGate runner heartbeat timer

[Timer]
OnBootSec=${INTERVAL}
OnUnitActiveSec=${INTERVAL}
AccuracySec=10

[Install]
WantedBy=timers.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable devgate-heartbeat.timer 2>/dev/null || true
    systemctl --user start devgate-heartbeat.timer

    log "Timer installed and enabled: devgate-heartbeat.timer"

    install_watchdog
}

# The inverted dead-man switch: this spoke checks the HUB, so a dead hub is
# noticed by a machine that is still up. Its own unit failing IS the signal
# (local-only by design — no GitHub issue, no token on the spoke).
install_watchdog() {
    local watchdog="$REPO_ROOT/scripts/hub-watchdog.sh"
    if [[ ! -x "$watchdog" ]]; then
        log "WARNING: $watchdog not found/executable — skipping hub watchdog install"
        return 0
    fi

    # Independent cadence from the heartbeat: the watchdog watches the HUB, so
    # it should not inherit a very short or very long heartbeat interval.
    # Clamped to [5 min, 15 min] — always well inside the script's staleness grace.
    if (( INTERVAL < 300 )); then WATCH_INTERVAL=300
    elif (( INTERVAL > 900 )); then WATCH_INTERVAL=900
    else WATCH_INTERVAL=$INTERVAL; fi

    log "Installing hub watchdog (checks the hub every ${WATCH_INTERVAL}s)..."

    # Runs the in-repo script directly; HUB_URL comes from the heartbeat env
    # file, which enrollment already wrote.
    cat > "$WATCHDOG_SERVICE_UNIT" <<EOF
[Unit]
Description=DevGate hub watchdog (spoke-side dead-man check)

[Service]
Type=oneshot
EnvironmentFile=$TICKET_FILE
ExecStart=$watchdog
EOF

    cat > "$WATCHDOG_TIMER_UNIT" <<EOF
[Unit]
Description=DevGate hub watchdog timer

[Timer]
OnBootSec=${WATCH_INTERVAL}
OnUnitActiveSec=${WATCH_INTERVAL}
AccuracySec=10

[Install]
WantedBy=timers.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable devgate-hub-watchdog.timer 2>/dev/null || true
    systemctl --user start devgate-hub-watchdog.timer

    log "Watchdog installed: devgate-hub-watchdog.timer (status: systemctl --user status devgate-hub-watchdog)"
}

# --- enroll mode --------------------------------------------------------------

if [[ "$MODE" == "enroll" ]]; then
    log "Enrolling '$RUNNER_NAME' with hub at $HUB_URL..."

    # JSON built by json.dumps: labels/host_alias are escaped, never spliced.
    PAYLOAD="$(json_payload "runner_name=$RUNNER_NAME" "repo=$REPO" \
        "enrollment_token=$ENROLL_TOKEN" "labels=$LABELS" \
        "host_alias=$HOST_ALIAS")"

    RESPONSE="$(post_json "$HUB_URL/enroll" "$PAYLOAD")" || {
        # The failure body never contains a token; safe to print.
        die "hub enrollment failed: $(printf '%s' "$RESPONSE" | response_summary)" 2
    }

    log "Hub response: $(printf '%s' "$RESPONSE" | response_summary)"

    # Extract heartbeat token from JSON response.
    HB_TOKEN="$(echo "$RESPONSE" | python3 -c 'import sys,json; print(json.load(sys.stdin)["heartbeat_token"])' 2>/dev/null)" || {
        die "could not parse heartbeat_token from hub response" 2
    }

    log "Enrolled successfully. Heartbeat token issued (not printed; written to $TICKET_FILE)."
    install_timer "$HB_TOKEN"
    log "Done. Runner '$RUNNER_NAME' is now heartbeating to $HUB_URL every ${INTERVAL}s."
fi

# --- revoke mode --------------------------------------------------------------

if [[ "$MODE" == "revoke" ]]; then
    log "Revoking runner '$REVOKE_RUNNER' from hub at $HUB_URL..."

    PAYLOAD="$(json_payload "runner_name=$REVOKE_RUNNER" \
        "heartbeat_token=$REVOKE_HB_TOKEN")"
    RESPONSE="$(post_json "$HUB_URL/revoke" "$PAYLOAD")" || {
        die "hub revoke failed: $(printf '%s' "$RESPONSE" | response_summary)" 2
    }
    log "Hub confirmed revocation: $(printf '%s' "$RESPONSE" | response_summary)"

    # Remove local timers + env file. The watchdog goes too: it reads
    # HUB_URL from the env file being deleted, so leaving it behind would
    # leave a unit that fails forever with a confusing config error.
    systemctl --user stop devgate-heartbeat.timer 2>/dev/null || true
    systemctl --user disable devgate-heartbeat.timer 2>/dev/null || true
    systemctl --user stop devgate-hub-watchdog.timer 2>/dev/null || true
    systemctl --user disable devgate-hub-watchdog.timer 2>/dev/null || true
    rm -f "$TIMER_UNIT" "$SERVICE_UNIT" "$TICKET_FILE" \
          "$WATCHDOG_TIMER_UNIT" "$WATCHDOG_SERVICE_UNIT"
    systemctl --user daemon-reload

    log "Runner '$REVOKE_RUNNER' revoked. Timers removed."
fi

exit 0
