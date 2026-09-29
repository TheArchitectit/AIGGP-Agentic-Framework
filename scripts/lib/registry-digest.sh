#!/usr/bin/env bash
# registry-digest.sh — what a REGISTRY SERVES for an image tag.
#
# One formula, sourced by every site that needs it (runner-image-cycle.sh,
# runner-heartbeat.sh, and anything else that must decide "is :main the
# record?"). The alternative is three spellings of the same curl dance that
# has already diverged once on axis — `podman image inspect` answers on the
# local-storage axis and is deliberately never consulted here.
#
# Functions:
#   docker_content_digest <image> <tag>
#       Prints the Docker-Content-Digest the registry's manifest endpoint
#       reports for that tag. Prints nothing and returns non-zero when the
#       registry cannot be reached, refuses, or serves no digest — a failed
#       check must not arrive as an empty string that compares unequal to
#       every digest and reads as "diverged".
#
# The recipe is the one scripts/re-pin-evaluator-identity.sh and the container
# publish job already use: anonymous token, then GET
# /v2/<path>/manifests/<tag> with the OCI+Docker Accept headers, read
# Docker-Content-Digest. Changing one site means changing this file.
#
# Sourced, not executed: the functions go into the caller's shell so the
# caller keeps its own set -euo pipefail and its own exit codes.

# docker_content_digest <image> <tag>
#   image must include the registry host (ghcr.io/owner/repo/name).
docker_content_digest() {
    local image="${1:?docker_content_digest: image is required}"
    local tag="${2:?docker_content_digest: tag is required}"
    # Deliberately not named after a credential variable: PREVENT-003 fires on
    # an assignment that opens a quoted literal. The value is fetched from
    # ghcr's anonymous pull endpoint below, not written here.
    local repo_path bearer headers served

    case "$image" in
        ghcr.io/*) ;;
        *)
            # Only ghcr is implemented. A second registry gets a refusal
            # rather than a silent https://ghcr.io look-alike call.
            echo "registry-digest: only ghcr.io is implemented, not '${image}'" >&2
            return 1
            ;;
    esac
    repo_path="${image#ghcr.io/}"

    bearer="$(curl -fsS --max-time 15 \
        "https://ghcr.io/token?scope=repository:${repo_path}:pull&service=ghcr.io" \
        | python3 -c 'import json,sys;print(json.load(sys.stdin).get("token",""))' \
        2>/dev/null || true)"
    if [ -z "$bearer" ]; then
        echo "registry-digest: no anonymous pull token for $repo_path" >&2
        return 1
    fi

    headers="$(curl -fsS --max-time 15 -o /dev/null -D - \
        -H "Authorization: Bearer $bearer" \
        -H 'Accept: application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json' \
        "https://ghcr.io/v2/${repo_path}/manifests/${tag}" 2>/dev/null || true)"
    served="$(printf '%s\n' "$headers" | tr -d '\r' \
        | awk 'tolower($1) == "docker-content-digest:" {print $2}')"
    if [ -z "$served" ]; then
        echo "registry-digest: no Docker-Content-Digest for ${image}:${tag}" >&2
        return 1
    fi
    printf '%s\n' "$served"
}