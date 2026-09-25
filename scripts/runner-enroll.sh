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
#   devgate-imgcycle-<name>.{service,timer}             the evaluator-image cycle
#   devgate-secretscan-<name>.{service,timer}           the fleet secret sweep
# The last two are installed but enabled only once the host is provisioned;
# `--help` names the variables that do it.
# Legacy fixed-name units (devgate-heartbeat.*, devgate-hub-watchdog.*) predate
# multi-runner hosts; those belonging to this runner are removed for it.
#
# ExecStart points at the copied helper, never an inline `bash -c`: systemd
# expands $ in ExecStart against the unit's own environment, so an inline body
# loses every variable it defines itself before bash runs it.
#
# Those installed units are not written here alone: scripts/lib/runner-units.sh
# holds every operation that writes into, or removes from, the host's unit/env
# namespace. This script decides WHAT a host runs (which runner, which hub,
# which token, which host may own a slug) and emits the heartbeat's and the
# image cycle's unit bodies; a unit that arrives whole with its own enablement
# rule (the watchdog, the fleet secret sweep) is emitted in the library, beside
# the rule that governs it. Enrollment already runs from a checkout
# (REPO_ROOT below), so the library sits beside it.
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
CYC_HELPER="$ENV_DIR/devgate-image-cycle.sh"
# The sweep and the gate it resolves as its own sibling. The gate's install
# name is `secret-scan.sh`, NOT `devgate-secret-scan.sh`, and that is
# load-bearing: the sweep resolves it by that literal name in its own
# directory, so any other name here is a helper that dies with "the gate script
# is not beside this one" on every tick. (Caught by running the installed copy;
# a test comparing the two files' presence, parent and bytes had passed.)
FLEET_HELPER="$ENV_DIR/devgate-secret-scan-fleet.sh"
GATE_HELPER="$ENV_DIR/secret-scan.sh"

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
CYC_SERVICE_UNIT=""
CYC_TIMER_UNIT=""
FLEET_SERVICE_UNIT=""
FLEET_TIMER_UNIT=""

# The cycle's interval is deliberately NOT the heartbeat's. A heartbeat is a
# cheap local POST that wants to be current; the cycle may pull an image over
# the network, so it converges on a slower beat and publishes nothing itself.
CYCLE_INTERVAL=3600

# And the sweep's is not the cycle's either, by the same logic taken further:
# one tick CLONES every declared repository, in full, to read its history. Daily
# is the cadence the question wants — "is there a credential sitting in a repo
# nobody has pushed to in months" does not change minute to minute — while a
# faster beat would spend a fleet's bandwidth to re-derive the same answer.
SWEEP_INTERVAL=86400

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
    CYC_SERVICE_UNIT="$STATE_DIR/devgate-imgcycle-$SLUG.service"
    CYC_TIMER_UNIT="$STATE_DIR/devgate-imgcycle-$SLUG.timer"
    FLEET_SERVICE_UNIT="$STATE_DIR/devgate-secretscan-$SLUG.service"
    FLEET_TIMER_UNIT="$STATE_DIR/devgate-secretscan-$SLUG.timer"
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

# Unit installation, helper copying and enable/disable live in one library:
# they are the half of this script that touches the host's unit namespace, and
# the half that grew past the file-size limit. Kept in the checkout beside this
# script, because enrollment already runs from a checkout (REPO_ROOT above).
UNIT_LIB="$SCRIPT_DIR/lib/runner-units.sh"
[[ -f "$UNIT_LIB" ]] || die "missing $UNIT_LIB — the unit installer; re-check out the repository" 3
# shellcheck source=lib/runner-units.sh
source "$UNIT_LIB"

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
  devgate-imgcycle-<name>, devgate-secretscan-<name>,
  devgate-heartbeat-<name>.env), so one host can enroll several runners.

  The evaluator-image cycle is INSTALLED here but enabled only once the host is
  provisioned: add COHERENCE_IMAGE, COHERENCE_IMAGE_MANIFEST_DIGEST and
  COHERENCE_PODMAN_STORE to the runner's environment file and run enroll again.
  The store is a per-fleet choice (templates/runner/README.md, design D3).

  The fleet secret sweep is installed the same way and for the same reason:
  add SECRET_SCAN_DECLARED=/path/to/declared-repos.txt (one repository URL per
  line) to the runner's environment file and run enroll again. Until then its
  units are on disk with no running timer — the sweep refuses to run on an
  empty declaration, so enabling it early would fail on every tick.

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

install_timer() {
    local hb_token="$1"

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

    # Both helpers must exist BEFORE their timers start: OnBootSec lies in the
    # past once uptime exceeds INTERVAL, so `systemctl start` fires the first
    # tick immediately, and an ExecStart with no target takes that run down.
    install_helper "Heartbeat" \
        "$REPO_ROOT/scripts/runner-heartbeat.sh" "$HB_HELPER"
    install_helper "Image-cycle" \
        "$REPO_ROOT/scripts/runner-image-cycle.sh" "$CYC_HELPER"
    # The gate first, then the sweep: the sweep resolves the gate as a sibling
    # at run time, so if only one of the two is ever missing it must not be the
    # gate. install_helper copies both in the same breath, and a missing source
    # is a die, so a checkout that lost either fails enrollment loudly here.
    install_helper "Secret-scan gate" \
        "$REPO_ROOT/scripts/secret-scan.sh" "$GATE_HELPER"
    install_helper "Fleet secret sweep" \
        "$REPO_ROOT/scripts/secret-scan-fleet.sh" "$FLEET_HELPER"

    # Write the heartbeat env file (mode 600 — it holds the token).
    #
    # This file is SHARED: the image cycle's three variables live in it too
    # (design D3.1 — one EnvironmentFile per runner), and nothing here enrolls
    # them, so an operator provisions a host by adding them by hand. A plain
    # `cat >` truncated that provisioning on every re-enroll, silently, and the
    # host then reported "not provisioned" for a mount that was mounted and a
    # store that was full. So the four keys this script OWNS are rewritten and
    # everything else in the file is carried over untouched.
    #
    # The rewrite goes to a temp file inside a subshell that sets umask 077, so
    # the token is never on disk with looser permissions than it ends with —
    # `cat > f` then `chmod 600 f` leaves it readable for the length of a
    # write. The `mv` is a rename within one directory, so it is atomic.
    local preserved=""
    if [[ -e "$TICKET_FILE" && ! -L "$TICKET_FILE" ]]; then
        preserved="$(grep -vE '^(HUB_URL|RUNNER_NAME|HEARTBEAT_TOKEN|LAST_JOB_SEEN)=' \
            "$TICKET_FILE" 2>/dev/null || true)"
    fi
    (
        umask 077
        {
            printf 'HUB_URL=%s\n' "$HUB_URL"
            printf 'RUNNER_NAME=%s\n' "$RUNNER_NAME"
            printf 'HEARTBEAT_TOKEN=%s\n' "$hb_token"
            printf 'LAST_JOB_SEEN=%s\n' ""
            if [[ -n "$preserved" ]]; then
                printf '# --- not managed by runner-enroll.sh; carried over as found ---\n'
                printf '%s\n' "$preserved"
            fi
        } > "$TICKET_FILE.new"
    )
    chmod 600 "$TICKET_FILE.new"
    mv -f "$TICKET_FILE.new" "$TICKET_FILE"

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

    # The image cycle (img-cycle-02, design D3). The gate never pulls
    # (coh-rt-01), so the pinned bytes have to be on the host before the job
    # starts; this is the out-of-band half, on the same one-EnvironmentFile-per-
    # runner contract the heartbeat uses (D3.1), which is why it reads the
    # file just written above.
    #
    # Its ExecStart is a bare path for the same reason the heartbeat's is.
    cat > "$CYC_SERVICE_UNIT" <<EOF
[Unit]
Description=DevGate runner evaluator-image cycle ($SLUG)

[Service]
Type=oneshot
EnvironmentFile=$TICKET_FILE
ExecStart=$CYC_HELPER
EOF

    cat > "$CYC_TIMER_UNIT" <<EOF
[Unit]
Description=DevGate runner evaluator-image cycle timer ($SLUG)

[Timer]
OnBootSec=${CYCLE_INTERVAL}
OnUnitActiveSec=${CYCLE_INTERVAL}
AccuracySec=60

[Install]
WantedBy=timers.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable "devgate-hb-$SLUG.timer" 2>/dev/null || true
    systemctl --user start "devgate-hb-$SLUG.timer"

    log "Heartbeat timer enabled: devgate-hb-$SLUG.timer (helper: $HB_HELPER)"

    enable_image_cycle
    install_fleet_sweep

    install_watchdog
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

    # Remove this runner's units + env file. The watchdog, the image cycle and
    # the fleet sweep go too: all three read the env file being deleted (the
    # sweep takes its --declared path from it), so leaving any of them behind
    # would leave a unit that fails forever with a confusing config error.
    systemctl --user stop "devgate-hb-$SLUG.timer" 2>/dev/null || true
    systemctl --user disable "devgate-hb-$SLUG.timer" 2>/dev/null || true
    systemctl --user stop "devgate-watchdog-$SLUG.timer" 2>/dev/null || true
    systemctl --user disable "devgate-watchdog-$SLUG.timer" 2>/dev/null || true
    systemctl --user stop "devgate-imgcycle-$SLUG.timer" 2>/dev/null || true
    systemctl --user disable "devgate-imgcycle-$SLUG.timer" 2>/dev/null || true
    systemctl --user stop "devgate-secretscan-$SLUG.timer" 2>/dev/null || true
    systemctl --user disable "devgate-secretscan-$SLUG.timer" 2>/dev/null || true
    rm -f "$TIMER_UNIT" "$SERVICE_UNIT" "$TICKET_FILE" \
          "$WATCHDOG_TIMER_UNIT" "$WATCHDOG_SERVICE_UNIT" \
          "$CYC_TIMER_UNIT" "$CYC_SERVICE_UNIT" \
          "$FLEET_TIMER_UNIT" "$FLEET_SERVICE_UNIT"
    remove_legacy_units "$REVOKE_RUNNER"
    systemctl --user daemon-reload

    log "Runner '$REVOKE_RUNNER' revoked. Units removed (devgate-hb-$SLUG.*, devgate-imgcycle-$SLUG.*, devgate-secretscan-$SLUG.*)."
fi

exit 0
