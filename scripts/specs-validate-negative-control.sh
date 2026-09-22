#!/usr/bin/env bash
# // spec: spec-fmt-04
# Specs-gate negative control (2026-09-20 drift audit).
#
# `openspec validate --all --strict` passing proves the tree is currently
# well-formed. It does NOT prove the validator would REFUSE malformed
# material: if the command were silently downgraded to a no-op, or resolved
# to something that always succeeds, the tree would keep validating green and
# nobody would know the gate had stopped working.
#
# This control feeds the same command a known-broken spec and requires a
# rejection that names the actual defect. The malformed input is
# tests/fixtures/malformed-spec/spec.md (no ## Purpose, no ## Requirements
# umbrella, a requirement-shaped level-2 heading) — staged into a throwaway
# store because the CLI resolves items BY NAME, never by file path.
#
# A nonzero exit alone is NOT sufficient proof: an unknown item also exits 1,
# so a mis-staged probe would pass vacuously. The control therefore requires
# the validator's own words for the fixture's designed defect.
#
# Exit: 0 = validator correctly refused and named the defect; 1 = anything
# else, including accepting the malformed spec or failing for the wrong
# reason.

set -uo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
fixture="$repo_root/tests/fixtures/malformed-spec/spec.md"

if [ ! -f "$fixture" ]; then
	echo "NEGATIVE CONTROL MISCONFIGURED: fixture not found at $fixture" >&2
	exit 1
fi

probe_root="$(mktemp -d)"
trap 'rm -rf "$probe_root"' EXIT

mkdir -p "$probe_root/openspec/specs/broken-probe"
cp "$fixture" "$probe_root/openspec/specs/broken-probe/spec.md"

# Run from the probe root so the broken spec is the only item in scope.
# Resolve the CLI the SAME binary the hard gate above it resolves to: the bin
# installed into the repo workspace by ci.yml's pinned `npm install --no-save`.
# A bare `npx openspec` is run from the probe root, where npx finds no local
# install and cannot resolve the name — CI's exact failure was npm's "could not
# determine executable to run". Locally that failure is masked by a globally
# installed openspec on PATH, which is how this shipped red once: the control
# must exercise the same binary the gate it vouches for runs, not whichever
# openspec happens to be on the invoking machine's PATH.
openspec_bin="$repo_root/node_modules/.bin/openspec"
if [ ! -x "$openspec_bin" ]; then
	echo "NEGATIVE CONTROL MISCONFIGURED: $openspec_bin not found." >&2
	echo "Install the pinned CLI first (mirroring ci.yml): npm install --no-save '@fission-ai/openspec@<pin>'" >&2
	exit 1
fi

out="$(cd "$probe_root" && "$openspec_bin" validate broken-probe --strict 2>&1)"
status=$?

if [ "$status" -eq 0 ]; then
	echo "NEGATIVE CONTROL FAILED: the validator ACCEPTED a malformed spec (exit 0)." >&2
	echo "The specs gate cannot be trusted to refuse bad input." >&2
	echo "$out" >&2
	exit 1
fi

if printf '%s' "$out" | grep -q "Unknown item"; then
	echo "NEGATIVE CONTROL MISCONFIGURED: the probe was staged wrong — the" >&2
	echo "validator rejected an unknown item, not the malformed fixture. A" >&2
	echo "nonzero exit from a mis-staged probe proves nothing." >&2
	echo "$out" >&2
	exit 1
fi

if ! printf '%s' "$out" | grep -q "Spec must have a Purpose section"; then
	echo "NEGATIVE CONTROL FAILED: the validator rejected the probe (exit $status)" >&2
	echo "but not for the fixture's designed defect (no ## Purpose section)." >&2
	echo "It must be doing real parsing, not failing for an unrelated reason." >&2
	echo "$out" >&2
	exit 1
fi

echo "negative control passed: strict validation refused the malformed fixture,"
echo "naming its designed defect (missing ## Purpose), exit $status."
