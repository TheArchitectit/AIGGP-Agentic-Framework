#!/usr/bin/env bash
# // spec: spec-state-01, spec-state-02, spec-state-03, spec-state-04, spec-state-05, spec-state-06
# Spec-state gate negative control (Gate 1.7).
#
# A gate that has only ever been run on a well-formed tree proves it accepts
# well-formed input, not that it refuses the shapes it exists to refuse. Each
# case below stages ONE defect into a throwaway repository and requires a
# rejection that names that defect in the gate's own words. A nonzero exit
# alone is not proof: a missing ledger, an unreadable revision, or a crash all
# exit nonzero, and each would pass a probe that only checks `!= 0`. Every
# assertion therefore matches the message the gate is designed to print.
#
# The fixture is minimal on purpose - two requirements, one closure table, one
# marked source file - so a failure here is a defect in the gate rather than in
# the fixture. It is built in `mktemp -d` and never touches the real tree.
#
# Cases (design section 1.7):
#   positive    valid row, real commits, sealed bundle            -> exit 0
#   1 cell-no-row       state edited, ledger untouched
#   2 row-no-cell       ledger appended, state untouched
#   3 same-commits      opened_commit == landed_commit
#   4 non-ancestor      landed_commit outside HEAD's ancestry
#   5 no-marker         opened..landed touches no file marked spec: <id>
#   6 bad-digest        the row pins a digest the bundle does not carry
#   6b skipped-test     the named test is recorded as skipped
#   7 partial-closure   Status: CLOSED while a requirement is WIRED
#   8 empty-scan        a range with no published specs exits 3, never 0
#
# Exit: 0 = every case rejected for the designed reason; 1 = anything else,
# including a case the gate accepted or rejected for a different reason.

set -uo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
devgate_root="$(cd "$script_dir/.." && pwd)"
gate="$devgate_root/scripts/spec_state_gate.py"

fixture="$(mktemp -d "${TMPDIR:-/tmp}/spec-state-nc.XXXXXX")"
trap 'rm -rf "$fixture"' EXIT
repo="$fixture/repo"
mkdir -p "$repo"
git -C "$repo" init -q
git -C "$repo" config user.email "control@example.invalid"
git -C "$repo" config user.name "spec-state control"
git -C "$repo" config commit.gpgsign false

failures=0
pass() { printf 'ok   %s\n' "$1"; }
fail() { printf 'FAIL %s\n' "$1"; failures=$((failures + 1)); }

# A sealed bundle the gate will accept: manifest objects carry the
# domain-tagged digest of their bytes, and the manifest digest is what a ledger
# row pins. Built with the repository's own canon so the control cannot drift
# from the validator's definition of "sealed". Prints the manifest digest.
make_bundle() {  # $1 = bundle dir, $2 = recorded status for the named test
  local dir="$1" status="${2:-passed}"
  mkdir -p "$dir"
  printf '{"tests": {"tests/test_demo.py::test_alpha": "%s"}}\n' "$status" > "$dir/tests.json"
  python3 - "$devgate_root" "$dir" <<'PY'
import sys
from pathlib import Path
devgate_root, bundle = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(devgate_root))
from hub.coherence import canon
objects = []
for path in sorted(bundle.iterdir()):
    if path.name == "evidence-manifest.json":
        continue
    objects.append({
        "path": path.name,
        "digest": canon.digest_bytes("evidence-manifest/v1", path.read_bytes()),
        "media_type": "application/json",
        "assertion_id": "spec-state-negative-control",
        "retention_class": "standard",
        "redacted": False,
    })
manifest = {"api_version": "devgate.spec-coherence.evidence/v1", "objects": objects}
(bundle / "evidence-manifest.json").write_text(
    canon.canon(manifest).decode("utf-8"), encoding="utf-8")
print(canon.digest_obj("evidence-manifest/v1", manifest))
PY
}

spec_text() {  # $1 demo-01 state, $2 demo-02 state, $3 document Status line
  cat <<EOF
# Demo capability

Status: $3

## Purpose

A fixture spec for the spec-state gate's negative control.

## Requirements

### Requirement: First behaviour
<!-- id: demo-01 -->

The system SHALL do the first thing.

### Requirement: Second behaviour
<!-- id: demo-02 -->

The system SHALL do the second thing.

## Requirement Closure

| Requirement | Status | Implementation | Verification |
|---|---|---|---|
| \`demo-01\` | $1 | \`src/demo.py\` | \`tests/test_demo.py\` |
| \`demo-02\` | $2 | \`src/demo.py\` | \`tests/test_demo.py\` |
EOF
}

row_json() {  # spec req from to opened landed evidence_digest tests_json
  python3 - "$@" <<'PY'
import json, sys
spec, req, frm, to, opened, landed, digest, tests = sys.argv[1:9]
row = {"schema": "v1", "spec": spec, "req": req, "from": frm, "to": to,
       "opened_commit": opened, "landed_commit": landed,
       "tests": json.loads(tests), "at": "2026-11-13T00:00:00Z"}
if digest:
    row["evidence"] = "evidence/bundle"
    row["evidence_digest"] = digest
print(json.dumps(row, separators=(",", ":")))
PY
}

# ---------------------------------------------------------------- base history
mkdir -p "$repo/openspec/specs/demo" "$repo/src" "$repo/tests"
printf '# devgate.spec-state-ledger/v1\n' > "$repo/openspec/state-ledger.jsonl"
spec_text WIRED WIRED "WIRED - under construction" > "$repo/openspec/specs/demo/spec.md"
printf '# spec: demo-01, demo-02\n\nvalue = 1\n' > "$repo/src/demo.py"
printf 'value = 1\n' > "$repo/src/unmarked.py"
printf 'def test_alpha():\n    assert True\n' > "$repo/tests/test_demo.py"
git -C "$repo" add -A
git -C "$repo" commit -q -m "fixture: base - both requirements WIRED"
git -C "$repo" branch -M base

# Detached, so building a fixture branch never advances `base` itself.
# The implementation window: a marked file changes, the spec does not.
git -C "$repo" checkout -q --detach base
printf '# spec: demo-01, demo-02\n\nvalue = 2\n' > "$repo/src/demo.py"
git -C "$repo" commit -q -am "fixture: work - marked file changes"
git -C "$repo" branch work

# A window that touches no marked file at all (case 5).
git -C "$repo" checkout -q --detach base
printf 'value = 3\n' > "$repo/src/unmarked.py"
git -C "$repo" commit -q -am "fixture: unmarked-only work"
git -C "$repo" branch work-unmarked

# A resolving commit outside HEAD's ancestry (case 4).
git -C "$repo" checkout -q --detach base
printf 'side = 1\n' > "$repo/src/side.py"
git -C "$repo" add -A
git -C "$repo" commit -q -m "fixture: side branch commit"
git -C "$repo" branch side

BASE="$(git -C "$repo" rev-parse base)"
UNMARKED="$(git -C "$repo" rev-parse work-unmarked)"
SIDE="$(git -C "$repo" rev-parse side)"

# A sealed bundle, committed so the tree the gate reads carries it.
git -C "$repo" checkout -q --detach work
mkdir -p "$repo/evidence"
DIGEST="$(make_bundle "$repo/evidence/bundle" passed | tail -1)"
git -C "$repo" add -A
git -C "$repo" commit -q -m "fixture: sealed evidence bundle"
git -C "$repo" branch -f work
WORK="$(git -C "$repo" rev-parse work)"

# --------------------------------------------------------------------- harness
stage() {  # $1 case name, $2 parent revision
  git -C "$repo" checkout -q -B "case-$1" "$2"
}

# run_case <case> <expected substring> <base revision>
run_case() {
  local name="$1" needle="$2" base_rev="$3" out rc
  out="$(python3 "$gate" --repo "$repo" --base "$base_rev" --head "case-$name" 2>&1)"
  rc=$?
  if [ "$rc" -ne 1 ]; then
    fail "$name: expected exit 1, got $rc - $out"
  elif ! printf '%s' "$out" | grep -qF -- "$needle"; then
    fail "$name: rejected without naming the defect (wanted: $needle) - $out"
  else
    pass "$name: $(printf '%s' "$out" | grep -m1 -F -- "$needle" | sed 's/^spec-state: VIOLATION - //')"
  fi
}

# --------------------------------------------------------- positive control
stage valid work
spec_text EXERCISED WIRED "WIRED - under construction" > "$repo/openspec/specs/demo/spec.md"
row_json demo demo-01 WIRED EXERCISED "$BASE" "$WORK" "$DIGEST" \
  '["tests/test_demo.py::test_alpha"]' >> "$repo/openspec/state-ledger.jsonl"
git -C "$repo" commit -q -am "fixture: valid transition"
out="$(python3 "$gate" --repo "$repo" --base work --head case-valid 2>&1)"; rc=$?
if [ "$rc" -eq 0 ]; then
  pass "positive-control: a sound transition is accepted ($out)"
else
  fail "positive-control: a sound transition was refused (exit $rc) - $out"
fi

# --------------------------------------------------------- 1. cell without row
stage cell-no-row work
spec_text EXERCISED WIRED "WIRED - under construction" > "$repo/openspec/specs/demo/spec.md"
git -C "$repo" commit -q -am "fixture: cell flipped, ledger untouched"
run_case cell-no-row "with no ledger row" work

# --------------------------------------------------------- 2. row without cell
stage row-no-cell work
row_json demo demo-01 WIRED EXERCISED "$BASE" "$WORK" "$DIGEST" \
  '["tests/test_demo.py::test_alpha"]' >> "$repo/openspec/state-ledger.jsonl"
git -C "$repo" commit -q -am "fixture: ledger appended, spec untouched"
run_case row-no-cell "a row with no state edit" work

# ------------------------------------------------------- 3. identical commits
stage same-commits work
spec_text EXERCISED WIRED "WIRED - under construction" > "$repo/openspec/specs/demo/spec.md"
row_json demo demo-01 WIRED EXERCISED "$WORK" "$WORK" "$DIGEST" \
  '["tests/test_demo.py::test_alpha"]' >> "$repo/openspec/state-ledger.jsonl"
git -C "$repo" commit -q -am "fixture: opened equals landed"
run_case same-commits "a transition must span two commits" work

# ---------------------------------------------------- 4. non-ancestor landing
stage non-ancestor work
spec_text EXERCISED WIRED "WIRED - under construction" > "$repo/openspec/specs/demo/spec.md"
row_json demo demo-01 WIRED EXERCISED "$BASE" "$SIDE" "$DIGEST" \
  '["tests/test_demo.py::test_alpha"]' >> "$repo/openspec/state-ledger.jsonl"
git -C "$repo" commit -q -am "fixture: landing commit off HEAD's ancestry"
run_case non-ancestor "is not an ancestor of" work

# --------------------------------------------------- 5. empty marker window
stage no-marker work-unmarked
spec_text EXERCISED WIRED "WIRED - under construction" > "$repo/openspec/specs/demo/spec.md"
row_json demo demo-01 WIRED EXERCISED "$BASE" "$UNMARKED" "$DIGEST" \
  '["tests/test_demo.py::test_alpha"]' >> "$repo/openspec/state-ledger.jsonl"
git -C "$repo" commit -q -am "fixture: transition with no marked source change"
run_case no-marker "carries 'spec: demo-01'" work-unmarked

# ------------------------------------------------------- 6. unsealed evidence
stage bad-digest work
spec_text EXERCISED WIRED "WIRED - under construction" > "$repo/openspec/specs/demo/spec.md"
ZERO_DIGEST="sha256:$(printf '0%.0s' {1..64})"
row_json demo demo-01 WIRED EXERCISED "$BASE" "$WORK" "$ZERO_DIGEST" \
  '["tests/test_demo.py::test_alpha"]' >> "$repo/openspec/state-ledger.jsonl"
git -C "$repo" commit -q -am "fixture: row pins a digest the bundle does not carry"
run_case bad-digest "evidence-validate.py rejected" work

# 6b. a named test recorded as skipped is not evidence of anything. The bundle
# is re-sealed so the row's digest is correct and only the status is wrong.
stage skipped-test work
spec_text EXERCISED WIRED "WIRED - under construction" > "$repo/openspec/specs/demo/spec.md"
SKIPPED_DIGEST="$(make_bundle "$repo/evidence/bundle" skipped | tail -1)"
row_json demo demo-01 WIRED EXERCISED "$BASE" "$WORK" "$SKIPPED_DIGEST" \
  '["tests/test_demo.py::test_alpha"]' >> "$repo/openspec/state-ledger.jsonl"
git -C "$repo" commit -q -am "fixture: the named test is recorded as skipped"
run_case skipped-test "not 'passed'" work

# ------------------------------------------------------- 7. partial closure
stage partial-closure work
spec_text EXERCISED WIRED "CLOSED (EXERCISED 2)" > "$repo/openspec/specs/demo/spec.md"
row_json demo demo-01 WIRED EXERCISED "$BASE" "$WORK" "$DIGEST" \
  '["tests/test_demo.py::test_alpha"]' >> "$repo/openspec/state-ledger.jsonl"
git -C "$repo" commit -q -am "fixture: spec declared CLOSED with one requirement WIRED"
run_case partial-closure "Status line says terminal" work

# --------------------------------------------------------- 8. vacuous scan
stage empty-tree work
git -C "$repo" rm -q -r openspec/specs
git -C "$repo" commit -q -m "fixture: no published specs at all"
out="$(python3 "$gate" --repo "$repo" --base work --head case-empty-tree 2>&1)"; rc=$?
if [ "$rc" -eq 3 ] && printf '%s' "$out" | grep -qF "empty scan is a failure"; then
  pass "empty-scan: zero specs exits 3, not 0"
else
  fail "empty-scan: expected exit 3 with the vacuity message, got $rc - $out"
fi

# ------------------------------------------------------- 9. unusable revision
# Exit 2 is the usage/config channel: it must not be confusable with a
# violation (1) or a vacuous pass (0/3).
out="$(python3 "$gate" --repo "$repo" --base deadbeefdeadbeef --head work 2>&1)"; rc=$?
if [ "$rc" -eq 2 ] && printf '%s' "$out" | grep -qF "does not resolve to a commit"; then
  pass "bad-revision: an unresolvable base exits 2 with a usage message"
else
  fail "bad-revision: expected exit 2 naming the revision, got $rc - $out"
fi

# ------------------------------------------------------ 10. unknown row field
# Gate 0 froze the field set; a gate that ignored a field it does not
# understand would let a producer record something nothing checks.
stage unknown-field work
spec_text EXERCISED WIRED "WIRED - under construction" > "$repo/openspec/specs/demo/spec.md"
row_json demo demo-01 WIRED EXERCISED "$BASE" "$WORK" "$DIGEST" \
  '["tests/test_demo.py::test_alpha"]' \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); r["reviewed_by"]="nobody"; print(json.dumps(r,separators=(",",":")))' \
  >> "$repo/openspec/state-ledger.jsonl"
git -C "$repo" commit -q -am "fixture: row carries a field outside schema v1"
run_case unknown-field "unknown field(s)" work

if [ "$failures" -ne 0 ]; then
  printf '\nspec-state negative control: %d case(s) FAILED\n' "$failures" >&2
  exit 1
fi
printf '\nspec-state negative control: every case rejected for the designed reason\n'
