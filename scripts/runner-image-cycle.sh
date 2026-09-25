#!/usr/bin/env bash
# runner-image-cycle.sh — keep the pinned evaluator image present on this host.
#
# WHY THIS EXISTS
# The coherence gate never pulls (coh-rt-01: the executed bytes must come from
# the registry pin, not from the network at gate time), so the pinned image has
# to be on the host *before* the job starts. Nothing used to put it there — not
# the runner templates, not runner-enroll.sh, not the hub — so an absent image
# showed up as a SKIPPED container phase on a host that otherwise looked
# healthy. This is the out-of-band half: a timer, installed beside the
# heartbeat, that converges the store on the RECORDED identity.
#
# THE RECORD IS THE DESIRED STATE, NOT A TAG.
# `container/execution-profiles.json` names the bytes a consumer fetches, and
# the driver resolves the digest-qualified ref — the tag is not in the executed
# path at all. So the target here is always `image@digest`, never `:main`, and a
# host holding a *different* build under the same repo is not converged.
#
# THE STORE IS AN INPUT, NOT AN ASSUMPTION (design D3)
# The runner is itself a container (templates/runner/self-hosted-runner.container)
# whose only volume is /_work — no podman socket, no storage mount — so podman on
# a runner host is not automatically the podman a job sees. Converging into a
# store the gate cannot read is exactly the failure this tick exists to prevent,
# and it looks identical to success from here. So the store is required and named
# (COHERENCE_PODMAN_STORE), every podman call is addressed to it with --root, and
# the tick first asks podman which graph root that actually is, failing closed if
# the answer is not the configured path. What exit 0 claims is therefore narrow
# and true: the recorded bytes are in the store named here. Whether that store is
# the one the runner container mounts is a property of the unit (Sprint 2.2),
# checked where the mount is declared, not something this script can discover.
#
# Required env (the unit's per-runner EnvironmentFile, alongside the heartbeat's):
#   COHERENCE_IMAGE, COHERENCE_IMAGE_MANIFEST_DIGEST, COHERENCE_PODMAN_STORE
# Optional:
#   IMAGE_CYCLE_PRUNE=0   keep superseded builds of the same repo (default: remove)
#
# Exit codes:
#   0   converged — the pinned digest-qualified ref is present in this store
#   1   configuration error (unset, non-digest identity, or a tag where a repo belongs)
#   2   podman is not available — this tick cannot be evaluated
#   3   the pinned ref could not be fetched
#   4   verification failed: the store does not hold the recorded bytes
#   5   store mismatch: podman's graph root is not COHERENCE_PODMAN_STORE
#   6   the configured store does not exist — refusing to create a mount
#   7   podman could not answer for the configured store (not a path mismatch)
# Each fault has its own code because each has its own fix: 5 edits a path,
# 6 fixes a mount, 7 asks why podman will not start. Collapsing them into one
# non-zero sends the operator to the wrong place.
# A non-zero exit is the honest state: the host cannot run the pinned evaluator.

set -euo pipefail

: "${COHERENCE_IMAGE:?COHERENCE_IMAGE is not set - check the unit EnvironmentFile}"
: "${COHERENCE_IMAGE_MANIFEST_DIGEST:?COHERENCE_IMAGE_MANIFEST_DIGEST is not set - check the unit EnvironmentFile}"
: "${COHERENCE_PODMAN_STORE:?COHERENCE_PODMAN_STORE is not set - check the unit EnvironmentFile}"

# A tag where a digest belongs would provision whatever the tag points at today
# — unreviewed bytes, reported as convergence. Refuse it before touching podman.
# The shape matters as much as the prefix: a truncated digest behaves like a
# wrong one at pull time and like a never-matching one at prune time, so the
# required shape is the one the registry actually serves.
HEX="${COHERENCE_IMAGE_MANIFEST_DIGEST#sha256:}"
REFUSED=""
case "$COHERENCE_IMAGE_MANIFEST_DIGEST" in
    sha256:*) ;;
    *) REFUSED="is not a digest" ;;
esac
case "$HEX" in
    ""|*[!0-9a-f]*) REFUSED="${REFUSED:-is not a digest}" ;;
esac
[ "${#HEX}" -eq 64 ] || REFUSED="${REFUSED:-is not a 64-hex sha256}"
if [ -n "$REFUSED" ]; then
    echo "[img-cycle] refused: COHERENCE_IMAGE_MANIFEST_DIGEST $REFUSED" \
         "('$COHERENCE_IMAGE_MANIFEST_DIGEST'). The record names bytes, not a tag." >&2
    exit 1
fi

# A repo here must be a repo: `repo:tag@sha256:…` is not a ref podman resolves
# by digest, and — measured 2026-09-24 — a tag in this variable silently stops
# the prune comparison from ever matching, which hides superseded builds.
case "${COHERENCE_IMAGE##*/}" in
    *:*)
        echo "[img-cycle] refused: COHERENCE_IMAGE carries a tag" \
             "('$COHERENCE_IMAGE'). Address a repository; the digest names the bytes." >&2
        exit 1
        ;;
esac

REF="$COHERENCE_IMAGE@$COHERENCE_IMAGE_MANIFEST_DIGEST"
PODMAN=(podman --root "$COHERENCE_PODMAN_STORE")

if ! command -v podman >/dev/null 2>&1; then
    echo "[img-cycle] podman not on PATH — cannot converge on $REF" >&2
    exit 2
fi

# The store is checked for EXISTENCE before podman is asked anything, and that
# order is the point: `podman --root X info` MATERIALISES X when it is missing
# (measured 2026-09-24 — one run left X/{db.sql,libpod} behind). The store is a
# mount, so on a host whose mount has not come up, creating an empty store is
# worse than answering wrongly: the pull below fills it, it outlives the mount,
# and the gate reads the mounted filesystem — which stays empty. The reason it
# yields ("pinned image absent") sends the operator to the pull path instead of
# to the mount.
if [ ! -d "$COHERENCE_PODMAN_STORE" ]; then
    echo "[img-cycle] store does not exist: $COHERENCE_PODMAN_STORE — refusing to" \
         "create it. The store is a mount; an empty one made here would outlive" \
         "the mount the gate reads." >&2
    exit 6
fi

# `canonical_dir <path>` — the directory a path names, so two spellings of one
# store compare equal. `cd`/`pwd` are shell BUILTINS, so a bare runner host
# gains no dependency. MEASURED 2026-09-24 on podman 6.1.1: `--root /tmp/ps1/`
# answers `/tmp/ps1` and `--root /tmp//ps1` answers `/tmp/ps1` too — podman
# NORMALISES. Comparing the two strings byte-for-byte therefore does not
# compare two stores: a trailing slash, an ordinary EnvironmentFile typo, made a
# correctly configured host refuse to converge. Falls back to the raw string
# when the path is not a directory, so a caller still gets a comparable answer.
canonical_dir() { (CDPATH= cd -- "$1" 2>/dev/null && pwd -P) || printf '%s' "$1"; }

# Fail closed on the store itself. `--root` is a request; this is the answer.
# `! var="$( … )"` is the status of the SUBSTITUTION, so a podman that fails no
# longer arrives as an empty string — which compared unequal to every configured
# store and so was reported as a mismatch, sending an operator to edit a path
# that was already correct.
if ! GRAPH_ROOT="$("${PODMAN[@]}" info --format '{{.Store.GraphRoot}}' 2>/dev/null)"; then
    echo "[img-cycle] podman could not answer for the configured store" \
         "'$COHERENCE_PODMAN_STORE' (not a path mismatch) — this tick cannot" \
         "verify which store it would fill" >&2
    exit 7
fi
if [ "$(canonical_dir "$GRAPH_ROOT")" != "$(canonical_dir "$COHERENCE_PODMAN_STORE")" ]; then
    echo "[img-cycle] store mismatch: podman reports graph root '${GRAPH_ROOT:-unknown}'," \
         "configured '$COHERENCE_PODMAN_STORE' — refusing to report convergence for a" \
         "store this tick cannot address" >&2
    exit 5
fi
unset GRAPH_ROOT

if "${PODMAN[@]}" image exists "$REF" >/dev/null 2>&1; then
    echo "[img-cycle] present: $REF"
else
    echo "[img-cycle] pulling: $REF"
    if ! "${PODMAN[@]}" pull --quiet "$REF"; then
        echo "[img-cycle] pull failed: $REF — the pinned bytes are not fetchable from here" >&2
        exit 3
    fi
fi

# Verify the IDENTITY, not merely presence: a ref that resolves to different
# bytes is not the pinned evaluator. Absent and mismatched are both failures —
# never a warning.
GOT="$("${PODMAN[@]}" image inspect --format '{{.Digest}}' "$REF" 2>/dev/null || true)"
if [ "$GOT" != "$COHERENCE_IMAGE_MANIFEST_DIGEST" ]; then
    echo "[img-cycle] verification failed: $REF resolves to '${GOT:-nothing}'," \
         "recorded '$COHERENCE_IMAGE_MANIFEST_DIGEST'" >&2
    exit 4
fi

# Reclaim disk from superseded builds of THIS repo only. A prune failure is
# reported and does not fail the tick: convergence is the contract, hygiene is
# not, and a build held by a running container must not turn a converged host
# red.
#
# MEASURED 2026-09-24 on real podman, three things this loop has to survive:
#   1. `podman images --filter reference=<repo>` is NOT repository-scoped. Asked
#      about `ghcr.io/.../devgate-coherence` it also listed
#      `localhost/devgate-coherence:latest` — the filter matches the image NAME,
#      crossing registries. So the listing is unscoped and the repository
#      comparison below is the actual scope guarantee; the filter bought nothing.
#   2. `podman rmi <id>` removes every name that ID carries — one ID can hold
#      both a registry pull and a local build. So an ID is only a candidate when
#      *every* row it appears in is scoped, or a human's tag dies with it.
#   3. A digest-pulled image that was never tagged lists with Tag `<none>`; one
#      that was pulled or built under a name lists WITH that name. MEASURED
#      2026-09-24, and this corrects what this comment used to claim: a LOCAL
#      BUILD DOES CARRY A DIGEST in this listing (`sha256:df67b148…` for a
#      `FROM scratch` build) — it is not "a tag and no digest". The Tag is
#      therefore the whole of the discrimination, and the digest comparison
#      below does NOT exclude local builds. Requiring `<none>` is what keeps a
#      locally built `devgate-coherence:<something>` — the same tag the CI
#      build job makes — out of the reap set.
#
# MEASURED 2026-09-24, and the reason the post-prune check below is not
# paranoia: for the same bytes, the LISTING's `.Digest` and `inspect`'s
# `.Digest` are different values (`sha256:294b683c…` vs `sha256:d56c381f…` for
# one alpine pull). So a store can legitimately list a digest that is not the
# recorded one for the image that IS the recorded bytes — which puts the pinned
# ID in `scoped` below and reaps it. `rmi <id>` takes every row that ID carries.
# The reap set is therefore decided by reasoning about podman's listing, and
# this repository does not accept reasoning in place of a check.
if [ "${IMAGE_CYCLE_PRUNE:-1}" = "1" ]; then
    declare -A scoped=() blocked=()
    while read -r id repo tag digest; do
        [ -n "${id:-}" ] || continue
        if [ "$repo" = "$COHERENCE_IMAGE" ] && [ "$tag" = "<none>" ] \
           && [ "$digest" != "$COHERENCE_IMAGE_MANIFEST_DIGEST" ]; then
            scoped["$id"]=1
        else
            blocked["$id"]=1
        fi
    done < <("${PODMAN[@]}" images \
                 --format '{{.ID}} {{.Repository}} {{.Tag}} {{.Digest}}' 2>/dev/null || true)

    # Iterating an EMPTY associative array this way was suspected of being an
    # unbound-variable error under `set -u` on bash 4.3, which would fail a
    # host that simply has nothing to reap. MEASURED 2026-09-24 in
    # docker.io/library/ubuntu:16.04 (bash 4.3.48): it is not — five variants
    # (`declare -A a=()`, bare `declare -A a`, the count, unquoted, and
    # emptied-after-use) all exit 0, and this script passes `bash -n` there.
    # No guard is added, because a guard no test can kill is decoration.
    for id in "${!scoped[@]}"; do
        if [ -n "${blocked[$id]:-}" ]; then
            continue
        fi
        "${PODMAN[@]}" rmi "$id" >/dev/null 2>&1 \
            || echo "[img-cycle] left in place (in use?): $id"
    done
    unset scoped blocked

    # The invariant the reap set was computed to preserve, checked instead of
    # assumed. Failing here is the difference between "a host lost its pinned
    # image and says so" and "a host lost its pinned image and reported
    # convergence" — and exit 0 is the one claim this script makes.
    if ! "${PODMAN[@]}" image exists "$REF" >/dev/null 2>&1; then
        echo "[img-cycle] verification failed after prune: the reap removed the" \
             "pinned image $REF from this store — this host can no longer gate" >&2
        exit 4
    fi
fi

# The success claim comes LAST, after every check that could contradict it. It
# used to be printed before the prune, so a run that reaped the pinned image
# announced "converged" and then exited 4 — the one line an operator greps for
# said the opposite of the exit code.
echo "[img-cycle] converged: $REF"
