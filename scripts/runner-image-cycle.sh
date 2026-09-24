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

# Fail closed on the store itself. `--root` is a request; this is the answer.
GRAPH_ROOT="$("${PODMAN[@]}" info --format '{{.Store.GraphRoot}}' 2>/dev/null || true)"
if [ "$GRAPH_ROOT" != "$COHERENCE_PODMAN_STORE" ]; then
    echo "[img-cycle] store mismatch: podman reports graph root '${GRAPH_ROOT:-unknown}'," \
         "configured '$COHERENCE_PODMAN_STORE' — refusing to report convergence for a" \
         "store this tick cannot address" >&2
    exit 5
fi

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
echo "[img-cycle] converged: $REF"

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
#   3. A digest-pulled image lists with Tag `<none>`, a local build lists with a
#      tag and no digest. Requiring `<none>` is what keeps a locally built
#      `devgate-coherence:<something>` — the same tag the CI build job makes —
#      out of the reap set.
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

    for id in "${!scoped[@]}"; do
        if [ -n "${blocked[$id]:-}" ]; then
            continue
        fi
        "${PODMAN[@]}" rmi "$id" >/dev/null 2>&1 \
            || echo "[img-cycle] left in place (in use?): $id"
    done
fi
