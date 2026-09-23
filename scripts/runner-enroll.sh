#!/usr/bin/env bash
# runner-enroll.sh — enroll a DevGate self-hosted runner with the monitor hub.
#
# Usage:
#   scripts/runner-enroll.sh <hub-url> <enrollment-token> [options]
#   scripts/runner-enroll.sh --revoke <hub-url> <heartbeat-token> <runner-name>
#
# Enrolls a runner (POST /enroll), stores its heartbeat token, and installs
# systemd user units that post a heartbeat every HEARTBEAT_INTERVAL_SEC
# (default 300s) and that watch the hub back.
#
# Every unit and env file is named from the runner, so one host can enroll
# several runners without enroll N overwriting enroll N-1's token:
#   ~/.config/containers/devgate-heartbeat-<name>.env   600, this runner's token
#   ~/.config/containers/devgate-heartbeat.sh           heartbeat helper (shared)
#   devgate-hb-<name>.{service,timer}                   the heartbeat
#   devgate-watchdog-<name>.{service,timer}             the hub watchdog
# Legacy fixed-name units (devgate-heartbeat.*, devgate-hub-watchdog.*) predate
# multi-runner hosts; those belonging to this runner are removed for it.
#
# ExecStart points at the copied helper, never an inline `bash -c`: systemd
# expands $ in ExecStart against the unit's own environment, so an inline body
# loses every variable it defines itself before bash runs it.
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
STATE_DIR="$HOME/.config/systemd/user"
ENV_DIR="$HOME/.config/containers"
HB_HELPER="$ENV_DIR/devgate-heartbeat.sh"

# Unit and env paths depend on the runner's name, which is not final until the
# arguments are parsed — set_unit_paths() derives SLUG and every path from it.
SLUG=""
SLUG_OWNER=""
SLUG_ATTRIBUTABLE="yes"
TICKET_FILE=""
SERVICE_UNIT=""
TIMER_UNIT=""
WATCHDOG_SERVICE_UNIT=""
WATCHDOG_TIMER_UNIT=""

set_unit_paths() {
    local name="$1"
    # SLUG keeps only characters systemd accepts in a unit name, so a runner
    # named "prod/web 1" does not silently produce an unusable unit.
    SLUG="$(printf '%s' "$name" | LC_ALL=C sed 's/[^A-Za-z0-9_-]/-/g')"
    [[ -n "$SLUG" ]] || die "runner name '$name' yields no usable unit name"
    TICKET_FILE="$ENV_DIR/devgate-heartbeat-$SLUG.env"
    SERVICE_UNIT="$STATE_DIR/devgate-hb-$SLUG.service"
    TIMER_UNIT="$STATE_DIR/devgate-hb-$SLUG.timer"
    WATCHDOG_SERVICE_UNIT="$STATE_DIR/devgate-watchdog-$SLUG.service"
    WATCHDOG_TIMER_UNIT="$STATE_DIR/devgate-watchdog-$SLUG.timer"
}

# Sets SLUG_OWNER to the RUNNER_NAME recorded at $TICKET_FILE ("" when no file
# exists there) and SLUG_ATTRIBUTABLE to "no" when a file DOES exist but names
# no runner — a torn write or tampering. Such a file may hold a token, so
# callers must refuse to overwrite or delete it: refusing beats losing it.
#
# This sets globals rather than printing, because a `die` inside "$( )" would
# only exit the subshell and leave the parent running.
#
# Distinct names can sanitize onto one unit set ("ci runner" and "ci/runner"),
# so every write or delete performed by slug consults this first.
slug_owner() {
    SLUG_OWNER=""
    SLUG_ATTRIBUTABLE="yes"
    # `-e` alone misses a dangling symlink, and a directory at this path would
    # otherwise read as "no file" — letting the enroll reach the hub before the
    # write fails, which is a ghost registration waiting to happen.
    if [[ ! -e "$TICKET_FILE" && ! -L "$TICKET_FILE" ]]; then
        return 0
    fi
    SLUG_OWNER="$(grep -E '^RUNNER_NAME=' "$TICKET_FILE" 2>/dev/null | cut -d= -f2- || true)"
    if [[ -z "$SLUG_OWNER" ]]; then
        SLUG_ATTRIBUTABLE="no"
    fi
}

log() { echo "[runner-enroll] $*"; }
die() { log "ERROR: $1"; exit "${2:-1}"; }

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

  Units and env are named per runner (devgate-hb-<name>, devgate-watchdog-<name>,
  devgate-heartbeat-<name>.env), so one host can enroll several runners.

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
    set_unit_paths "$RUNNER_NAME"
elif [[ "$MODE" == "revoke" ]]; then
    [[ -n "$HUB_URL" ]] || { usage; }
    [[ -n "$REVOKE_HB_TOKEN" ]] || die "heartbeat token required for revoke" 1
    [[ -n "$REVOKE_RUNNER" ]] || die "runner name required for revoke" 1
    set_unit_paths "$REVOKE_RUNNER"
fi

# --- helpers ------------------------------------------------------------------

post_json() {
    local url="$1" payload="$2"
    # --max-time bounds a hung hub: without it a stuck connection wedges
    # the systemd oneshot unit indefinitely (audit hardening).
    curl -sf --connect-timeout 5 --max-time 15 -X POST \
        -H 'Content-Type: application/json' \
        -d "$payload" "$url" 2>&1
}

# Retire the pre-multi-runner fixed-name units. They cannot coexist with the
# per-runner layout: both read the single ~/.devgate-heartbeat.env, so a second
# enroll overwrites the first runner's token and the wrong runner reports.
remove_legacy_units() {
    local only="${1:-}"
    local -a legacy=(
        "$STATE_DIR/devgate-heartbeat.service"
        "$STATE_DIR/devgate-heartbeat.timer"
        "$STATE_DIR/devgate-hub-watchdog.service"
        "$STATE_DIR/devgate-hub-watchdog.timer"
    )
    local f present=0
    for f in "${legacy[@]}"; do [[ -e "$f" ]] && present=1; done
    (( present )) || return 0

    # Touch only what belongs to the runner being acted on (or is orphaned) —
    # another runner on this host may still depend on the legacy units. A file
    # we cannot attribute gets the same refusal as the per-runner path: an
    # unreadable owner check must not be read as permission to delete. `-e` and
    # `-L` rather than `-f`, so a directory or dangling symlink here is treated
    # as "names no runner" instead of as "nothing to protect".
    if [[ -e "$HOME/.devgate-heartbeat.env" || -L "$HOME/.devgate-heartbeat.env" ]]; then
        local owner
        owner="$(grep -E '^RUNNER_NAME=' "$HOME/.devgate-heartbeat.env" 2>/dev/null | cut -d= -f2- || true)"
        if [[ -z "$owner" ]]; then
            log "Legacy env at $HOME/.devgate-heartbeat.env names no runner — left in place"
            return 0
        fi
        if [[ "$owner" != "$only" ]]; then
            log "Legacy units belong to '$owner' (not '$only') — left in place"
            return 0
        fi
    fi

    log "Removing legacy fixed-name units (they cannot coexist with per-runner units)"
    systemctl --user stop devgate-heartbeat.timer 2>/dev/null || true
    systemctl --user disable devgate-heartbeat.timer 2>/dev/null || true
    systemctl --user stop devgate-hub-watchdog.timer 2>/dev/null || true
    systemctl --user disable devgate-hub-watchdog.timer 2>/dev/null || true
    # Only the units go. ~/.devgate-heartbeat.env is deliberately left behind:
    # it may still hold another runner's token, and removing a token file on the
    # strength of a possibly-unreadable owner check is not a risk worth taking.
    rm -f "${legacy[@]}" \
          "$STATE_DIR/timers.target.wants/devgate-heartbeat.timer" \
          "$STATE_DIR/timers.target.wants/devgate-hub-watchdog.timer"
    systemctl --user daemon-reload 2>/dev/null || true
}

install_timer() {
    local hb_token="$1"
    local helper_src="$REPO_ROOT/scripts/runner-heartbeat.sh"
    [[ -f "$helper_src" ]] || die "missing $helper_src — cannot install the heartbeat helper" 3

    log "Installing systemd user units for '$RUNNER_NAME' (interval=${INTERVAL}s)..."

    remove_legacy_units "$RUNNER_NAME"
    mkdir -p "$STATE_DIR" "$ENV_DIR"

    # Defense in depth — the same check runs before the hub POST, but this one
    # guards the actual write.
    slug_owner
    if [[ "$SLUG_ATTRIBUTABLE" == "no" ]]; then
        die "file at $TICKET_FILE names no runner, so its ownership is unknown — inspect it and remove it if stale" 1
    fi
    if [[ -n "$SLUG_OWNER" && "$SLUG_OWNER" != "$RUNNER_NAME" ]]; then
        die "slug '$SLUG' already belongs to '$SLUG_OWNER' — refusing to overwrite; pick a distinct --runner-name so the two do not share one token" 1
    fi

    # The helper must exist BEFORE the timer starts: OnBootSec lies in the past
    # once uptime exceeds INTERVAL, so `systemctl start` fires the first tick
    # immediately, and an ExecStart with no target takes that run down with it.
    if [[ -x "$HB_HELPER" ]]; then
        if ! cmp -s "$helper_src" "$HB_HELPER"; then
            log "WARNING: $HB_HELPER differs from scripts/runner-heartbeat.sh — future helper fixes will not reach this host until it is removed"
        fi
        log "Heartbeat helper present, left unchanged: $HB_HELPER"
    else
        install -m 755 "$helper_src" "$HB_HELPER"
        log "Heartbeat helper installed: $HB_HELPER"
    fi

    # Write the heartbeat env file (chmod 600 — contains the token).
    cat > "$TICKET_FILE" <<EOF
HUB_URL=$HUB_URL
RUNNER_NAME=$RUNNER_NAME
HEARTBEAT_TOKEN=$hb_token
LAST_JOB_SEEN=""
EOF
    chmod 600 "$TICKET_FILE"

    # ExecStart is a bare path on purpose. systemd expands $ in ExecStart
    # against the unit's own environment, so an inline `bash -c` body loses
    # every variable it defines itself (DISK_OK, PODMAN_OK) before bash runs:
    # the JSON goes out malformed, the hub rejects it, and the unit exits 22 on
    # every tick while enrollment still reports success.
    cat > "$SERVICE_UNIT" <<EOF
[Unit]
Description=DevGate runner heartbeat ($SLUG)

[Service]
Type=oneshot
EnvironmentFile=$TICKET_FILE
ExecStart=$HB_HELPER
EOF

    # Timer unit: fires every INTERVAL seconds.
    cat > "$TIMER_UNIT" <<EOF
[Unit]
Description=DevGate runner heartbeat timer ($SLUG)

[Timer]
OnBootSec=${INTERVAL}
OnUnitActiveSec=${INTERVAL}
AccuracySec=10

[Install]
WantedBy=timers.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable "devgate-hb-$SLUG.timer" 2>/dev/null || true
    systemctl --user start "devgate-hb-$SLUG.timer"

    log "Heartbeat timer enabled: devgate-hb-$SLUG.timer (helper: $HB_HELPER)"

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
Description=DevGate hub watchdog (spoke-side dead-man check, $SLUG)

[Service]
Type=oneshot
EnvironmentFile=$TICKET_FILE
ExecStart=$watchdog
EOF

    cat > "$WATCHDOG_TIMER_UNIT" <<EOF
[Unit]
Description=DevGate hub watchdog timer ($SLUG)

[Timer]
OnBootSec=${WATCH_INTERVAL}
OnUnitActiveSec=${WATCH_INTERVAL}
AccuracySec=10

[Install]
WantedBy=timers.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable "devgate-watchdog-$SLUG.timer" 2>/dev/null || true
    systemctl --user start "devgate-watchdog-$SLUG.timer"

    log "Watchdog installed: devgate-watchdog-$SLUG.timer (status: systemctl --user status devgate-watchdog-$SLUG)"
}

# --- enroll mode --------------------------------------------------------------

if [[ "$MODE" == "enroll" ]]; then
    log "Enrolling '$RUNNER_NAME' with hub at $HUB_URL..."

    # Labels are passed RAW to json.dumps below (audit hardening): a comma,
    # quote, or backslash inside a label must survive as data.

    # Check BEFORE contacting the hub: a refused enroll must not leave behind a
    # registered runner that will never heartbeat from this host.
    slug_owner
    if [[ "$SLUG_ATTRIBUTABLE" == "no" ]]; then
        die "file at $TICKET_FILE names no runner, so its ownership is unknown — inspect it and remove it if stale" 1
    fi
    if [[ -n "$SLUG_OWNER" && "$SLUG_OWNER" != "$RUNNER_NAME" ]]; then
        die "slug '$SLUG' already belongs to '$SLUG_OWNER' — refusing to overwrite; pick a distinct --runner-name so the two do not share one token" 1
    fi

    # Built by json.dumps (audit hardening): a quote or backslash in a
    # label produces valid JSON and can never break out of the string.
    PAYLOAD="$(python3 - "$RUNNER_NAME" "$REPO" "$ENROLL_TOKEN" "$LABELS" "$HOST_ALIAS" <<'PY'
import json, sys
labels = [x.strip() for x in sys.argv[4].split(",") if x.strip()]
print(json.dumps({
    "runner_name": sys.argv[1],
    "repo": sys.argv[2],
    "enrollment_token": sys.argv[3],
    "labels": labels,
    "host_alias": sys.argv[5],
}))
PY
)"

    RESPONSE="$(post_json "$HUB_URL/enroll" "$PAYLOAD")" || {
        die "hub enrollment failed: $RESPONSE" 2
    }

    # Print only non-secret fields (audit hardening): the enroll response
    # carries the heartbeat token, which must never hit stdout/CI scrollback.
    log "Hub response: $(printf '%s' "$RESPONSE" | python3 -c '
import json, sys
try:
    doc = json.loads(sys.stdin.read())
except Exception:
    print("(unparseable response)"); raise SystemExit
print(json.dumps({k: v for k, v in doc.items()
                  if k in ("ok", "runner_name", "error", "detail")}))
')"

    # Extract heartbeat token from JSON response.
    HB_TOKEN="$(echo "$RESPONSE" | python3 -c 'import sys,json; print(json.load(sys.stdin)["heartbeat_token"])' 2>/dev/null)" || {
        die "could not parse heartbeat_token from hub response" 2
    }

    log "Enrolled successfully. Heartbeat token issued."
    install_timer "$HB_TOKEN"
    log "Done. Runner '$RUNNER_NAME' is now heartbeating to $HUB_URL every ${INTERVAL}s."
fi

# --- revoke mode --------------------------------------------------------------

if [[ "$MODE" == "revoke" ]]; then
    log "Revoking runner '$REVOKE_RUNNER' from hub at $HUB_URL..."

    PAYLOAD="{\"runner_name\":\"$REVOKE_RUNNER\",\"heartbeat_token\":\"$REVOKE_HB_TOKEN\"}"
    RESPONSE="$(post_json "$HUB_URL/revoke" "$PAYLOAD")" || {
        die "hub revoke failed: $RESPONSE" 2
    }
    log "Hub confirmed revocation: $RESPONSE"

    # The local names derive from the runner being revoked, so a *different*
    # runner whose name sanitizes to the same slug would have its units and
    # token file deleted here — the very clobber the per-runner layout exists
    # to prevent. Never remove files that belong to someone else.
    slug_owner
    if [[ "$SLUG_ATTRIBUTABLE" == "no" ]]; then
        log "Local file $TICKET_FILE names no runner — leaving it alone."
        log "Only the hub-side token for '$REVOKE_RUNNER' was revoked; no local files were touched."
        exit 0
    fi
    if [[ -n "$SLUG_OWNER" && "$SLUG_OWNER" != "$REVOKE_RUNNER" ]]; then
        log "Local units/env at slug '$SLUG' belong to '$SLUG_OWNER', not '$REVOKE_RUNNER'"
        log "Left in place — only the hub-side token for '$REVOKE_RUNNER' was revoked."
        exit 0
    fi

    # Remove this runner's units + env file. The watchdog goes too: it reads
    # HUB_URL from the env file being deleted, so leaving it behind would
    # leave a unit that fails forever with a confusing config error.
    systemctl --user stop "devgate-hb-$SLUG.timer" 2>/dev/null || true
    systemctl --user disable "devgate-hb-$SLUG.timer" 2>/dev/null || true
    systemctl --user stop "devgate-watchdog-$SLUG.timer" 2>/dev/null || true
    systemctl --user disable "devgate-watchdog-$SLUG.timer" 2>/dev/null || true
    rm -f "$TIMER_UNIT" "$SERVICE_UNIT" "$TICKET_FILE" \
          "$WATCHDOG_TIMER_UNIT" "$WATCHDOG_SERVICE_UNIT"
    remove_legacy_units "$REVOKE_RUNNER"
    systemctl --user daemon-reload

    log "Runner '$REVOKE_RUNNER' revoked. Units removed (devgate-hb-$SLUG.*)."
fi

exit 0
