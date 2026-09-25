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
# Optional env, all three or none (the image cycle's, supplied by the same
# EnvironmentFile once the host is provisioned) — see the image probe below:
#   COHERENCE_IMAGE, COHERENCE_IMAGE_MANIFEST_DIGEST, COHERENCE_PODMAN_STORE
#
# Exit codes:
#   0   hub accepted the heartbeat (HTTP 200)
#   1   required env missing — the unit's EnvironmentFile was not read
#   22  hub answered with a non-200
#   *   curl's own code when the hub could not be reached (still a failure —
#       a heartbeat that did not happen must never look like a pass)
#
# An unreported IMAGE is deliberately not in that list. See the probe.

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

# The evaluator image this host would gate with (img-cycle-03, design D5).
#
# REPORTED, never enforced. Every failure below becomes an absence WITH A
# REASON and the tick still exits 0 — a heartbeat that dies blinds the whole
# fleet, which is strictly worse than an image field that reads unknown. So
# this is the one probe here whose failure is not an exit code.
#
# The reasons use the cycle's own vocabulary (runner-image-cycle.sh: config,
# store mismatch, pull) because each names a different fix: a fleet view
# saying only "no image" would send an operator looking at all of them. Each
# fault below therefore gets its own reason — a podman that will not start is
# NOT a wrong store path, and rendering it as one sends the operator to edit a
# path that was already correct.
#
# Which directory does a path name? cd/pwd are shell BUILTINS, so this adds no
# dependency to a host's PATH — and `pwd -P` answers about the real directory,
# which is the question the job container will ask. It matters because the two
# sides of the comparison are not spellings of the same string: podman
# NORMALISES the graph root it reports (measured 2026-09-24, podman 6.1.1:
# `--root /tmp/ps1/` answers `/tmp/ps1`, and `--root /tmp//ps1` answers
# `/tmp/ps1` too). Compared as raw strings, a trailing slash — an ordinary
# EnvironmentFile typo — makes a correctly provisioned host report a mismatch,
# and because that branch skips the presence check the host reads as unable to
# gate until someone edits a path that was already right.
#
# null is a positive report. A host that converged and then lost its image
# reports null with a reason, and the hub must let that CLEAR a stored ref —
# otherwise the stale digest stays on the dashboard reading ready-to-gate.
# canonical_dir <path> — the directory a path names, for comparing two
# spellings of it. `cd`/`pwd` are builtins, so nothing new is required on PATH
# (this host may be a bare runner); `pwd -P` resolves symlinks, which is the
# question "does this name denote the store the job reaches". Falls back to
# the raw string when the path is not a directory, so a caller that skipped the
# existence check still gets a comparable answer rather than an empty one.
canonical_dir() { (CDPATH= cd -- "$1" 2>/dev/null && pwd -P) || printf '%s' "$1"; }

image_digest=""
image_reason=""
if [ -z "${COHERENCE_IMAGE:-}" ] || [ -z "${COHERENCE_IMAGE_MANIFEST_DIGEST:-}" ] \
    || [ -z "${COHERENCE_PODMAN_STORE:-}" ]; then
    # Name the ones that are actually unset, and only those: a reason listing
    # variables that are in fact set sends the operator to the wrong line.
    missing=""
    [ -n "${COHERENCE_IMAGE:-}" ] || missing="${missing:+$missing, }COHERENCE_IMAGE"
    [ -n "${COHERENCE_IMAGE_MANIFEST_DIGEST:-}" ] \
        || missing="${missing:+$missing, }COHERENCE_IMAGE_MANIFEST_DIGEST"
    [ -n "${COHERENCE_PODMAN_STORE:-}" ] \
        || missing="${missing:+$missing, }COHERENCE_PODMAN_STORE"
    image_reason="not provisioned: $missing not set"
    unset missing
elif ! command -v podman >/dev/null 2>&1; then
    image_reason="podman not on PATH"
else
    # Ask podman which graph root --root resolves to before asking it anything
    # about the image. A host configured with the wrong store would otherwise
    # answer "the ref is present" about a store its own gate never reads —
    # green probe, gate cannot serve (design D3.1).
    #
    # The store is checked for EXISTENCE first, and that order is the point:
    # `podman --root X info` materialises X when it is missing (measured — one
    # run left X/{db.sql,libpod} behind). On a host whose store mount has not
    # come up, creating an empty store is worse than answering wrongly: it
    # survives on the underlying filesystem after the mount appears, and the
    # reason it yields ("pinned image absent") sends the operator to the pull
    # path instead of to the mount.
    pinned_ref="${COHERENCE_IMAGE}@${COHERENCE_IMAGE_MANIFEST_DIGEST}"
    # `! var="$( ... )"` is the status of the substitution: a podman that
    # fails no longer arrives as an empty string, which compared unequal to
    # every configured store and so was reported as a mismatch.
    if [ ! -d "$COHERENCE_PODMAN_STORE" ]; then
        image_reason="store does not exist: $COHERENCE_PODMAN_STORE"
    elif ! graph_root="$(podman --root "$COHERENCE_PODMAN_STORE" info \
            --format '{{.Store.GraphRoot}}' 2>/dev/null)"; then
        image_reason="podman info failed for the configured store (not a path mismatch)"
    elif [ "$(canonical_dir "$graph_root")" != "$(canonical_dir "$COHERENCE_PODMAN_STORE")" ]; then
        image_reason="store mismatch: podman reports graph root '${graph_root:-<none>}'"
        image_reason="$image_reason, configured '$COHERENCE_PODMAN_STORE'"
    elif ! podman --root "$COHERENCE_PODMAN_STORE" image exists "$pinned_ref" \
        >/dev/null 2>&1; then
        image_reason="pinned image absent from the store (not pulled)"
    else
        image_digest="$pinned_ref"
    fi
    unset graph_root pinned_ref
fi

# The empty strings become JSON null: `or None` rather than a sentinel string,
# so a consumer testing for null gets null and not "null".
#
# The fleet sweep's state rides here too (secret-scan-07), read from the report
# the sweep leaves on disk. Its three cases are deliberately three different
# things, and collapsing any pair is how a fleet reads clean while blind:
#
#   SECRET_SCAN_REPORT unset -> the key is still sent, as null. Absence is a
#       POSITIVE report ("this host has no scan state"), which is what lets the
#       hub clear a stale one to unknown. A key left out entirely means the
#       opposite — "this spoke does not report scan state" — so the hub keeps
#       what it had, which is right for an older helper and wrong here.
#   the file is missing     -> null as well: the sweep has not run on this host.
#   the file will not parse -> `unreadable`, NOT an empty fleet. The sweep
#       rewrites this file on its own timer while this tick reads it, so a
#       reader meeting a half-written file is a live case; an empty repos list
#       would have been indistinguishable from "every repository is clean".
#
# Each repository is reduced to its state, and NOT its locations: the report
# keeps rule/path/line/commit so an operator on the host can act, and the
# heartbeat ships the fact that repository X has an uncovered secret without
# carrying every finding's file path across the network on every tick.
#
# None of it can fail the tick. As with the image probe, a heartbeat that dies
# blinds the whole fleet, which is worse than a state that reads unknown.
body="$(python3 -c 'import json, os, sys

def scan_state(path):
    # No `if not path` guard: an unset SECRET_SCAN_REPORT reaches here as the
    # empty string, and open("") raises FileNotFoundError — which is the same
    # answer this function gives for a file that is not there, and the right
    # one. A branch that returns None before the try would be a second way to
    # say the same thing, and nothing could tell which of the two ran.
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        repos = doc["repos"]
        if not isinstance(repos, list):
            # The hub predicate requires the same thing for the same reason
            # (scan_state_unknown in hub/registry.py): a report whose repos is
            # not a list has no repositories to render, and "no repositories"
            # is what a dashboard shows as clean. Raising routes it to the
            # `unreadable` branch below rather than returning an empty fleet.
            # No apostrophes in here: this whole snippet lives in a
            # single-quoted python3 -c, and one would end it mid-function.
            raise ValueError("repos is not a list")
        return {"repos": [{
            "name": r["name"], "state": r["state"],
            "reason": r.get("reason"), "scope": r.get("scope"),
            "scanned_at": r.get("scanned_at"),
            "findings": r.get("findings", 0),
            "uncovered": r.get("uncovered", 0),
        } for r in repos], "unreadable": None}
    except FileNotFoundError:
        return None
    except Exception as exc:
        return {"repos": [], "unreadable": f"{type(exc).__name__}: {exc}"}

print(json.dumps({
    "runner_name": os.environ["RUNNER_NAME"],
    "heartbeat_token": os.environ["HEARTBEAT_TOKEN"],
    "disk_ok": sys.argv[1] == "true",
    "podman_ok": sys.argv[2] == "true",
    "image_digest": sys.argv[3] or None,
    "image_reason": sys.argv[4] or None,
    "scan_state": scan_state(os.environ.get("SECRET_SCAN_REPORT", "")),
}))' "$disk_ok" "$podman_ok" "$image_digest" "$image_reason")"

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
