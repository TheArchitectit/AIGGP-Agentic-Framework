#!/usr/bin/env bash
# // spec: fw-prov-01
#
# scripts/release_preflight.sh — the artifact checks the tag path must never
# skip. Called by deploy.sh after `git add -A` and before the release commit,
# because both checks judge the INDEX (what is about to be tagged), not the
# working tree.
#
# R12 — CHECKSUMS.sha256 is documented as generated at tag time, but nothing on
# the tag path generated it. It shipped stale from 2026-11-01 to 2026-11-13: a
# consumer running the verify line the manifest itself prints found 38 digests
# that disagreed with the tree and 18 shipped scripts it did not list at all.
# Regenerate, verify, and stage the manifest so the release commit carries the
# digests of the tree being tagged.
#
# fw-prov-01 — on a host with core.fileMode=false, editing a shebang'd file and
# re-staging it records 100644 and silently drops the bit; v1.3.33 shipped
# exactly that and CI's Exec-bit integrity step failed on the release commit.
#
# Exit: 0 both checks pass; non-zero otherwise (deploy.sh runs under -e).

set -euo pipefail

if [ -f scripts/gen-checksums.py ]; then
	out="$(python3 scripts/gen-checksums.py generate 2>&1)" || {
		printf '%s\n' "$out" >&2
		echo "[preflight] FAIL: could not generate CHECKSUMS.sha256 — refusing to tag release artifacts whose digests are unknown" >&2
		exit 1
	}
	echo "[preflight] $out"
	python3 scripts/gen-checksums.py verify >/dev/null || {
		echo "[preflight] FAIL: the generated CHECKSUMS.sha256 does not verify against the tree — refusing to tag it" >&2
		exit 1
	}
	git add CHECKSUMS.sha256
fi

if [ -f scripts/check_exec_bits.py ]; then
	if ! out="$(python3 scripts/check_exec_bits.py 2>&1)"; then
		printf '%s\n' "$out" >&2
		echo "[preflight] FAIL: exec-bit integrity — the release commit would drop a shebang's 100755 (fix each file with the command above)" >&2
		exit 1
	fi
	echo "[preflight] $out"
fi

# Open-item gates at release preflight (placement decision 2026-11-15). These
# two gates read files a checkout contains, so they run here as well as in the
# push-time CI job. Stated precisely: the push-time job DETECTS a violation
# after it has already landed on main and cannot block anything; THIS preflight
# runs before the release commit and tag, so a red gate here refuses the
# release. That is a real block, on the operator release path only.
#
# FAIL CLOSED: a missing gate script or missing decided input is a hard error.
# Nothing-scanned (exit 3) is not green here either.

if [ -f scripts/secret_rotation_check.py ]; then
	if ! out="$(python3 scripts/secret_rotation_check.py docs/secret-rotation.jsonl 2>&1)"; then
		printf '%s\n' "$out" >&2
		echo "[preflight] FAIL: secret-rotation state — a scrubbed secret is not a revoked secret (see docs/secret-rotation.jsonl)" >&2
		exit 1
	fi
	echo "[preflight] $out"
else
	echo "[preflight] FAIL: required gate script missing: scripts/secret_rotation_check.py — a missing gate is a hard error, never a silent pass" >&2
	exit 1
fi

if [ -f scripts/evidence_claim_check.py ]; then
	if ! out="$(python3 scripts/evidence_claim_check.py --root . --allow docs/evidence-claim-allowlist.txt 2>&1)"; then
		printf '%s\n' "$out" >&2
		echo "[preflight] FAIL: evidence-claim state — an unevidenced DEFERRED/MOCK/STUB/TODO marker is in the tree being released" >&2
		exit 1
	fi
	echo "[preflight] $out"
else
	echo "[preflight] FAIL: required gate script missing: scripts/evidence_claim_check.py — a missing gate is a hard error, never a silent pass" >&2
	exit 1
fi
