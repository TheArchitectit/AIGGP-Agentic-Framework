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
# Optional env:
#   ADDRESS  this runner's routable (tailnet) address, published so the hub
#            can resolve services for this runner's host_alias
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

# dirname(1) is a PATH dependency these scripts cannot afford: a bare host
# with an empty PATH must still reach the podman check. Builtins only.
_self="${BASH_SOURCE[0]}"
_script_dir="${_self%/*}"
[ "$_script_dir" = "$_self" ] && _script_dir=.
SCRIPT_DIR="$(cd -- "$_script_dir" && pwd)"
unset _self _script_dir
# Same sibling rule as runner-image-cycle.sh: in-repo it is lib/registry-digest.sh,
# installed it is copied beside the helper as registry-digest.sh (runner-enroll.sh
# installs it). Missing from a host one of them ticks.
if [ -f "$SCRIPT_DIR/lib/registry-digest.sh" ]; then
    # shellcheck source=lib/registry-digest.sh
    . "$SCRIPT_DIR/lib/registry-digest.sh"
elif [ -f "$SCRIPT_DIR/registry-digest.sh" ]; then
    # shellcheck source=registry-digest.sh
    . "$SCRIPT_DIR/registry-digest.sh"
else
    echo "[hb] registry-digest.sh missing beside this script ($SCRIPT_DIR)" \
         "— img-cycle-05 divergence not checked" >&2
    # Not a dead heartbeat. The fleet needs the tick more than the advisory;
    # the field below is simply left absent (could not check ≠ agrees).
    registry_digest_missing=1
fi

# The toolchain probe (mon-tc-01, design "Detection"), sourced under the same
# sibling rule. Missing is the same non-fatal shape: the gap fields stay
# absent from the body, which the hub reads as "no opinion this tick" — never
# as a complete toolchain. A host whose installed copy lost this library keeps
# ticking; it just stops talking about its toolchain, which is the honest
# degradation.
if [ -f "$SCRIPT_DIR/lib/toolchain_probe.py" ]; then
    TOOLCHAIN_PROBE_LIB="$SCRIPT_DIR/lib/toolchain_probe.py"
elif [ -f "$SCRIPT_DIR/toolchain_probe.py" ]; then
    TOOLCHAIN_PROBE_LIB="$SCRIPT_DIR/toolchain_probe.py"
else
    echo "[hb] toolchain_probe.py missing beside this script ($SCRIPT_DIR)" \
         "— toolchain gaps not probed this tick" >&2
    TOOLCHAIN_PROBE_LIB=""
fi

: "${HUB_URL:?HUB_URL is not set - check the unit EnvironmentFile}"
: "${RUNNER_NAME:?RUNNER_NAME is not set - check the unit EnvironmentFile}"
: "${HEARTBEAT_TOKEN:?HEARTBEAT_TOKEN is not set - check the unit EnvironmentFile}"

# Both scratch filenames must be filesystem-safe, and both are computed here
# because the probe below needs the same name the POST below writes its response
# to. A name containing "/" makes curl unable to open the -o target (exit 23),
# and set -e turns that into a dead tick before the HTTP status is even checked.
safe_name="$(printf '%s' "$RUNNER_NAME" | LC_ALL=C sed 's/[^A-Za-z0-9_-]/-/g')"
resp="${TMPDIR:-/tmp}/devgate-hb-last-resp-${safe_name}.json"

# --- toolchain probe (mon-tc-01, spoke side) ---------------------------------
#
# The required list is NOT kept here. mon-tc-01 makes the vocabulary and the
# profile table the hub's spec-governed data, so the hub echoes this lane's
# reviewed profile in its /heartbeat response and the tick caches that echo
# (the same "hub response is read" move the row-count echo made first); the
# probe below only ever sees what the hub itself stated. A first tick after
# enrollment has no cache yet, so it sends no gap fields (absent ≠ empty:
# mon-tc-06 says absence means the hub has no evidence, and a tick that sent
# [] before probing anything would report a clean lane out of thin air); the
# echo that arrives with it seeds the next tick. That is one cadence of
# silence after enrollment, which the fleet already tolerates for coverage.
#
# None of it can fail the tick: a probe failure ends as absent fields, not a
# dead heartbeat, exactly as with the image probe above.
required_cache="${TMPDIR:-/tmp}/devgate-hb-required-${safe_name}.json"
missing_tools_json=""
probe_complete_json=""
if [ -n "$TOOLCHAIN_PROBE_LIB" ] && [ -f "$required_cache" ]; then
    # The cache read is defensive: a torn or hand-edited file yields no probe
    # run and absent fields, never a partial probe. probe_tool only ever
    # executes the fixed commands the spec names, and only under the bound.
    probe_out="$(TOOLCHAIN_PROBE_LIB_PATH="$TOOLCHAIN_PROBE_LIB" python3 -c '
import json, os, sys, importlib.util
spec = importlib.util.spec_from_file_location(
    "toolchain_probe", os.environ["TOOLCHAIN_PROBE_LIB_PATH"])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        required = json.load(fh).get("required_tools") or []
except Exception:
    sys.exit(0)  # absent fields: no opinion, not an empty one
missing, complete = mod.probe_required(required)
print(json.dumps({"missing": missing, "complete": complete}))
' "$required_cache" 2>/dev/null || true)"
    if [ -n "$probe_out" ]; then
        missing_tools_json="$(printf '%s' "$probe_out" | python3 -c \
            'import json,sys; d=json.load(sys.stdin); print(json.dumps(d["missing"]))' \
            2>/dev/null || true)"
        probe_complete_json="$(printf '%s' "$probe_out" | python3 -c \
            'import json,sys; d=json.load(sys.stdin); print("true" if d["complete"] else "false")' \
            2>/dev/null || true)"
    fi
fi
unset probe_out

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

# img-cycle-05: served-vs-recorded rides this ticker (design D5). Non-empty
# means "the published tag has moved past the record"; the tick still exits 0 —
# it is a fact about the repository, not a fault on this host. Empty means
# either "checked and they agree" or "could not check"; the lib's failure is
# reported on stderr and the key becomes null, which is NOT a clean bill of
# health and is exactly why a missing lib is not a dead heartbeat above.
image_pin_divergence=""
if [ -n "${COHERENCE_IMAGE:-}" ] && [ -n "${COHERENCE_IMAGE_MANIFEST_DIGEST:-}" ] \
    && [ "${registry_digest_missing:-0}" != "1" ] \
    && [ "${IMAGE_CYCLE_SKIP_ADVISORY:-0}" != "1" ]; then
    PublishedTag="${COHERENCE_PUBLISHED_TAG:-main}"
    served_digest="$(docker_content_digest "${COHERENCE_IMAGE}" "${PublishedTag}" || true)"
    if [ -n "${served_digest:-}" ] && [ "$served_digest" != "$COHERENCE_IMAGE_MANIFEST_DIGEST" ]; then
        image_pin_divergence="served ${COHERENCE_IMAGE}:${PublishedTag} is $served_digest but the record is $COHERENCE_IMAGE_MANIFEST_DIGEST — a re-pin is due"
    fi
    unset PublishedTag served_digest
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

def gap_fields():
    # The two toolchain fields travel as a pair or not at all. An empty gap list
    # is still SENT: it is the positive report that this image has everything the
    # hub itself said this lane requires, and dropping it would turn a provisioned
    # lane back into the no-evidence state (mon-tc-06 separates those two on
    # purpose). The companion flag is the probe run outcome and is the only way
    # the hub can ever learn a run was incomplete: it cannot infer that from the
    # list it is handed. A tick that could not probe sends NEITHER field — absent,
    # not empty and not false. It has no opinion, which is not the same as a
    # negative one, and a value invented here would be a fabricated health reading.
    #
    # The parse is guarded because this snippet has no right to kill the tick: a
    # probe that printed garbage yields absent fields, same as a probe that never
    # ran. No apostrophes anywhere in this function - it lives in a single-quoted
    # python3 -c, and one would end the snippet mid-function.
    raw = sys.argv[6] if len(sys.argv) > 6 else ""
    if not raw:
        return {}
    try:
        tools = json.loads(raw)
    except Exception:
        return {}
    return {"missing_tools": tools,
            "missing_tools_probe_complete": sys.argv[7] == "true"}

print(json.dumps({
    "runner_name": os.environ["RUNNER_NAME"],
    "heartbeat_token": os.environ["HEARTBEAT_TOKEN"],
    "disk_ok": sys.argv[1] == "true",
    "podman_ok": sys.argv[2] == "true",
    "image_digest": sys.argv[3] or None,
    "image_reason": sys.argv[4] or None,
    "image_pin_divergence": sys.argv[5] or None,
    "scan_state": scan_state(os.environ.get("SECRET_SCAN_REPORT", "")),
    "address": os.environ.get("ADDRESS") or None,
    **gap_fields(),
}))' "$disk_ok" "$podman_ok" "$image_digest" "$image_reason" "$image_pin_divergence" \
    "$missing_tools_json" "$probe_complete_json")"


code="$(curl -sS -o "$resp" -w '%{http_code}' -X POST \
    -H 'Content-Type: application/json' \
    -d "$body" \
    "$HUB_URL/heartbeat")"

echo "[hb:$RUNNER_NAME] HTTP $code"
if [ "$code" != "200" ]; then
    echo "[hb:$RUNNER_NAME] hub response: $(cat "$resp" 2>/dev/null || true)" >&2
    exit 22
fi

# --- seed the next tick's probe (mon-tc-01, spoke side) -----------------------
#
# This is the other half of the echo read above: the hub has now said, for this
# lane, which tools its own record requires, and the next tick probes exactly
# that. Written to a scratch file rather than kept in memory because a tick is one
# process that exits — there is no other place for the value to live between two
# systemd runs 300s apart.
#
# Three outcomes, and the third one is the reason this is a function call and not
# a `cp`:
#   * a list   -> cache it, and the next tick probes it;
#   * null     -> the hub has NO reviewed assignment for this lane. That is not an
#                 empty requirement, and caching it as one would make an
#                 unassigned lane report "my image has everything", which is
#                 mon-tc-01's `profile-unassigned` rendered as complete. The cache
#                 is REMOVED, so the next tick sends no gap fields again;
#   * absent   -> a hub predating the echo. Same treatment: no cache, no opinion,
#                 and never a guess built from the spoke's own PATH.
#
# A write failure is silent and non-fatal for the same reason the probe is: the
# fleet needs this tick more than it needs next tick's coverage.
if [ -n "$TOOLCHAIN_PROBE_LIB" ]; then
    if python3 - "$resp" "$required_cache" <<'PY'
import json, os, sys

resp_path, cache_path = sys.argv[1], sys.argv[2]
try:
    with open(resp_path, encoding="utf-8") as fh:
        required = json.load(fh).get("required_tools")
except Exception:
    sys.exit(1)
if not isinstance(required, list):
    # null (no reviewed profile) or absent (old hub): refuse to invent one.
    sys.exit(1)
tmp = cache_path + ".tmp"
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump({"required_tools": required}, fh)
os.replace(tmp, cache_path)
PY
    then
        :
    elif [ -f "$required_cache" ]; then
        # Stale is worse than none here: a cached list the hub has since retracted
        # would keep the spoke reporting a gap its own record no longer requires.
        rm -f "$required_cache" 2>/dev/null || true
    fi
    unset required_cache
fi
