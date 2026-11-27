# Proposal

## Why

Three gate-tooling defects reported by NeonDash during its gap analysis
(2026-11-24/25), all the same family: a gate whose numbers or silence cannot
be trusted by the CI step that runs it.

1. **The phantom uncovered.** `spec_traceability.py` summed its denominator
   per spec file while its numerator intersected a deduped set of ids. A
   change package that legitimately restates a sealed requirement (a MODIFIED
   delta under its own capability name) is stated twice and covered once by
   that arithmetic, so a tree with nothing uncovered reported
   `49/51 requirements covered` plus `advisory — 2 uncovered` while its own
   `--report` detail said every id was covered. The summary disagreed with the
   tool's own evidence.
2. **The silent hygiene gate.** `failure_registry_check.py` prints nothing on
   success. Nothing — so a CI step cannot require a scope line, and
   "validated 68 entries" is indistinguishable from "found no registry and
   shrugged" (the audit that added the explicit-path guard found the same
   vacuous-green shape once already). NeonDash worked around it in yaml: the
   workflow counts the merged input files itself (`wc -l` of bundled plus
   overlay) and asserts that number before running the gate. Scope that lives
   in every consumer's workflow is scope the tool forgot to own.
3. **The anchors that fit none.** `spec_gap_scan.py`'s inventory anchors are
   hardcoded game dirs (`src/autoload`, `src/core`, …). A repo shaped like
   NeonDash — code under `scripts/`, tools under `tools/` — yields zero
   anchors, exit 2, "unknown scope", forever. Honest by SGA-04's design, and
   therefore permanently ignored, which is the outcome a gate must not settle
   for. The fleet already has one scope contract per repo
   (`.guardrails/scope.json`, fw-scope-01) carrying `skip_dirs`,
   `source_dirs` and `size_overrides`, and the size gate was pulled out of the
   identical hole on 2026-11-13 by declaring its roots there.

## What Changes

- `spec_traceability.py`: the summary's numerator counts requirement
  **statements**, the same thing its denominator counts; when ids are stated
  by more than one spec, the summary line says how many, so the number is
  never a mystery. Blocking still fails per statement; the failure list stays
  deduped (naming one id twice tells a reader nothing new).
- `failure_registry_check.py`: `check()` records what it looked at and
  `main()` prints a scope line on **every** exit path, green included, before
  any findings. Consumers may now `grep '^failure-registry: scope: '` instead
  of counting files; NeonDash deletes its yaml arithmetic in the same move.
- `spec_gap_scan.py`: a new optional `inventory_dirs` key in the fleet's
  existing `.guardrails/scope.json` replaces the game-shaped defaults; the
  scanner reports which set it used, and its honest empty names it too. A
  malformed or escaping declaration is a configuration error (exit 2), never a
  silent fall back to the defaults — that would discard exactly the scope the
  project just declared. `coh-sec-01` containment applies as it does to the
  size gate's walk roots.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rule-coverage-truth`: the covered/total summary counts one kind of thing.
- `gate-execution-contract`: a hygiene gate evidences its own input scope.
- `gate-configuration-contract`: a scanner's swept surface is declared, not
  assumed, and comes from the one scope contract the repo already has.

## Impact

- `scripts/spec_traceability.py`, `scripts/failure_registry_check.py`,
  `scripts/spec_gap_scan.py`, and their three test files (negative controls
  for each defect class, planted as the fleet does: the test fails before the
  fix and names the shape of the lie after it).
- Consumer-visible output changes: NeonDash's summary line grows a
  parenthetical; its registry step gains a line it can require. No exit-code
  changes except a malformed `inventory_dirs` declaration, which is new input
  and could not have been misbehaving before.
- Game-shaped repos see nothing: no `inventory_dirs` key, no behaviour change.
