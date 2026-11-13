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
