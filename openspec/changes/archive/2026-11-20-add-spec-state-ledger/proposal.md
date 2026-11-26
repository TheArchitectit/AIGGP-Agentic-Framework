# Change: Bind Spec State Transitions to Commits and Evidence

> **Status:** Proposed specification only. No gate, generator, hook, or ledger is
> implemented by this package, and no existing spec is reclassified by it.

## Why

Spec lifecycle state is a free-text edit with no verifiable basis. At audited
revision `7d3ebc5`, nothing in the tree connects a spec's state to the work it
claims:

- `openspec validate --all --strict` validates format only. It passed 33 items
  without evaluating state semantics or repository history.
- `scripts/spec_traceability.py` maps requirement IDs (`<!-- id: ... -->`) to
  `// spec: <id>` source markers, but its default mode is `advisory` and the
  opt-in file `openspec/gate-config.json` is absent, so no capability blocks.
- No spec-related script reads git history at all. `spec_traceability.py`,
  `spec_gap_scan.py`, `findings_to_spec.py`, and `evidence-validate.py` contain
  zero `git log`, `git diff`, `git show`, or `git rev-parse` invocations.
- `core.hooksPath` is unset, so no pre-commit enforcement path exists.
- No test under `tests/` references an opening commit, a landing commit, a
  transition, or a ledger.

The consequence: `Status: CLOSED` and a `Requirement Closure` table are
assertions a person types. At `7d3ebc5`, 28 of 31 specs carry a closure table
(112 `**EXERCISED**` cells) and `openspec/INDEX.md` reports
`CLOSED 31 - PARTIAL 0 - OPEN 0 - UNKNOWN 0`. That is a fully closed program
with no auditable link from any cell to the commit that implemented it or the
run that exercised it. A spec can be closed with zero work and no gate objects.

`openspec/INDEX.md` compounds the problem. Its header states
"**Generated, not typed**" and describes derivation from closure cells, but no
generator exists in the tree. The file is hand-maintained, which is the exact
failure mode its header disclaims.

This change specifies what would make a transition trustworthy: an append-only
ledger, a gate that derives transitions from the diff and verifies both bounding
commits, evidence that the requirement was exercised rather than asserted, and a
generator that makes the index claim true.

## What Changes

- **Spec state becomes ledgered data, not prose.** A new
  `openspec/state-ledger.jsonl` records one row per requirement transition with
  the opening commit, the landing commit, the tests exercised, and a sealed
  evidence reference. The five existing cell values
  (`EXERCISED`/`WIRED`/`ABSENT`/`NOT_RUN`/`DIFFERS`) are reused unchanged; no
  new vocabulary is introduced.
- **A gate reconciles the diff against the ledger.** `scripts/spec_state_gate.py`
  derives which requirements changed state by diffing the spec tree between a
  base revision and `HEAD`, and requires a matching ledger row in the same
  range. Editing the cell without the row fails, and adding the row without the
  cell fails, so neither record can be trusted alone.
- **Both bounding commits must resolve and be distinct.** The opening commit
  must be a strict ancestor of the landing commit, the landing commit must be an
  ancestor of `HEAD`, and the two must differ. This is the enforceable form of
  "a commit before and a commit after": it rejects declaring a requirement
  complete in the same commit that implements it.
- **Work must land where the requirement says it lives.** The diff between the
  bounding commits must touch a file carrying that requirement's own
  `// spec: <id>` marker, reusing the marker contract
  `scripts/spec_traceability.py` already defines rather than introducing a
  parallel mapping.
- **Closure requires exercised evidence.** A terminal transition must reference
  a sealed bundle that `scripts/evidence-validate.py` accepts with exit `0` and
  that carries a passing record for every named test. The gate reuses the one
  reviewed evidence mechanism in the tree instead of defining a weaker parallel
  authority.
- **`openspec/INDEX.md` becomes generated.** `scripts/spec_index.py` renders it
  from the ledger and closure tables, with a `--check` mode that fails on drift.
  The file's current "Generated, not typed" claim becomes true, or is corrected
  to match reality.
- **Enforcement placement is stated honestly.** Because this repository takes
  direct pushes to `main` with no pull-request gate, a push-time job detects a
  transition that already landed and MUST NOT be described as preventing it. A
  local hook blocks but is bypassable, with CI named as the audit trail.

## Outcome and scope

- Define an append-only state ledger committed with the spec edit, recording
  `from`, `to`, an opening commit, a landing commit, the tests exercised, and a
  sealed evidence reference for every transition.
- Specify `scripts/spec_state_gate.py`: derive transitions from
  `git diff <base>..HEAD -- openspec/`, require a matching ledger row, require
  both commits to resolve and be ordered, require the landing commit to touch
  source carrying the requirement's own `// spec: <id>` marker, require a
  verifiable evidence bundle, and require closure of the whole spec rather than
  a subset of its requirements.
- Specify `scripts/spec_index.py` so `openspec/INDEX.md` is generated from the
  ledger and closure tables, plus a drift check that fails when the committed
  index disagrees with regeneration.
- Define the migration that backfills provable transitions and marks the rest
  explicitly unproven; define a ratchet so a spec with a ledger row cannot
  revert to free-text authority.

This package specifies the contract and the enforcement order. It does not
write the gate, the generator, the hook, or any backfilled ledger row.

## Exclusions

No change to the meaning of `EXERCISED`, `WIRED`, `ABSENT`, `NOT_RUN`, or
`DIFFERS` cell values, and no new state vocabulary. No reclassification of the
31 current specs by this package. No change to `openspec validate` semantics, no
new required field that would invalidate an existing archive package, and no
change to the release gate in `scripts/deploy.sh`. No hosted service, database,
or external store; the ledger is a file in the tree.

## Dependencies and release gate

The ledger format freezes before any gate is written. The gate and its negative
control land together, because an unproven gate is not a gate. Index generation
lands after the gate so the generator reads a validated ledger rather than
laundering an invalid one. Enforcement placement (pre-commit hook or push-time
CI) is an owner decision recorded in `design.md` section 8 and precedes any
claim that a transition is blocked rather than only reported.

A green unit suite is insufficient. The gate is not complete until its negative
control rejects a forged closure for the reason it was designed to detect.

## Audit map at `7d3ebc5`

- Format-only validation: `openspec validate --all --strict` reports
  `Totals: 33 passed, 0 failed (33 items)`.
- Advisory traceability: `scripts/spec_traceability.py:36-40` returns
  `{"default_mode": "advisory", "specs": {}}` when the config is absent;
  `openspec/gate-config.json` is absent.
- No history access: verified by grep for `git (log|diff|show|rev-parse)` and
  `subprocess.*git` across the four spec scripts; all return zero.
- Closure tables present: 28 of 31 specs under `openspec/specs/*/spec.md`
  contain a `## Requirement Closure` table; 112 `**EXERCISED**` cells total.
- Status-line exceptions: `openspec/specs/doc-truth/spec.md:3`,
  `openspec/specs/per-screen-tracking/spec.md`,
  `openspec/specs/zig-opengl-engine/spec.md` carry a `Status:` line and no
  closure table.
- Index claim versus tree: `openspec/INDEX.md:3-5` asserts generated status; no
  writer for `INDEX.md` exists in any source file, and the only other reference
  is prose in `HANDOFF-AIGGP-Agentic-Framework.md`.
- No enforcement path: `git config core.hooksPath` is unset; `.git/hooks`
  contains no active hook.
- Existing evidence machinery to reuse: `scripts/evidence-validate.py`
  (frozen exit codes `0` valid, `1` invalid, `30` usage,
  `scripts/evidence-validate.py:37-39`).
