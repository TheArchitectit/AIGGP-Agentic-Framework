# Tasks: Bind Spec State Transitions to Commits and Evidence

Status is per-task below, not a blanket label. **Every task in this package is
open (`- [ ]`)**: this is a specification-only change. No gate, generator, hook,
or ledger row is implemented here, and no existing spec is reclassified.

Evidence file:line notes are inline against audited revision `7d3ebc5`. Gates
are ordered; no later gate upgrades an earlier failed gate.

## Sprint summary

| Sprint | Gate | Focus | Effort | Priority | Depends on |
|--------|------|-------|--------|----------|------------|
| S-L0 | Gate 0 | Freeze ledger schema and state vocabulary | S | P0 | — |
| S-L1 | Gate 1 | `spec_state_gate.py` + negative control | L | P0 | S-L0 |
| S-L2 | Gate 2 | Index generation and drift check | M | P0 | S-L1 |
| S-L3 | Gate 3 | Enforcement placement and hook wiring | M | P0 | S-L1 |
| S-L4 | Gate 4 | Migration of the 31 existing specs | L | P1 | S-L1–S-L3 |

**Global stop rule:** No gate is complete without its exit criteria and named
evidence. A failed, blocked, or stopped gate freezes all later gates. Do not
reclassify a failure as skipped or waived to proceed.

## Gate 0 — Freeze the ledger contract (blocking)

**Sprint:** S-L0 | **Effort:** S | **Priority:** P0
**Entry criteria:** This proposal accepted; no ledger exists in the tree.
**Exit criteria:** The `v1` row schema is frozen in `design.md` section 1 with
the exact field set (`schema`, `spec`, `req`, `from`, `to`, `opened_commit`,
`landed_commit`, `tests`, `evidence`, `at`); the `to` vocabulary is confirmed as
exactly `EXERCISED | WIRED | ABSENT | NOT_RUN | DIFFERS`, matching the 112
existing `**EXERCISED**` cells; an empty `openspec/state-ledger.jsonl` exists
with a one-line schema comment so the diff base always resolves.
**Dependencies:** None (first gate; must complete before S-L1–S-L4).
**Stop conditions:** Any state value invented beyond the frozen five → reject
and re-freeze. Any field that stores a timestamp used for ordering → reject;
commit ancestry is the only ordering source.

- [ ] 0.1 Freeze the `openspec/state-ledger.jsonl` row schema `v1` in `design.md` section 1: exact field set, required versus optional, and the rejection rule for unknown fields.
- [ ] 0.2 Confirm the transition vocabulary is exactly the five existing cell values and record that no new state word is added by this change.
- [ ] 0.3 Add an empty `openspec/state-ledger.jsonl` with a one-line schema comment so every diff has a resolvable base for the ledger file itself.
- [ ] 0.4 Record that `at` is informational only and MUST NOT be used for ordering; ancestry is the sole ordering source.

## Gate 1 — The gate itself, with a control that proves it can fail (blocking)

**Sprint:** S-L1 | **Effort:** L | **Priority:** P0
**Entry criteria:** Gate 0 exited; ledger schema frozen.
**Exit criteria:** `scripts/spec_state_gate.py` implements all six checks —
transition-by-diff reconciliation, bounding-commit resolution and ordering,
distinctness of the two commits, marked-source change within the window,
sealed-evidence verification via `scripts/evidence-validate.py` exit `0`, and
whole-spec terminality. Exit codes frozen as `0` pass, `1` violation, `2` usage
or config error, `3` nothing scanned. A negative control
(`scripts/spec-state-validate-negative-control.sh`, modelled on
`scripts/specs-validate-negative-control.sh`) stages seven forged cases and
requires rejection naming the designed defect for each.
**Dependencies:** S-L0.
**Stop conditions:** Any control case passing → stop; the gate is not a gate. A
gate that cannot reject a forged closure MUST NOT ship as blocking.

- [ ] 1.1 Implement diff-derived transition detection: compute changed requirements by diffing the spec tree between a base revision and `HEAD`, and reconcile that set against ledger rows added in the same range.
- [ ] 1.2 Implement bounding-commit verification: both commits resolve, `opened_commit` is a strict ancestor of `landed_commit`, `landed_commit` is an ancestor of `HEAD`, and the two are distinct.
- [ ] 1.3 Implement the marked-source check: the `opened_commit..landed_commit` diff must touch a file carrying `// spec: <req-id>` or `# spec: <req-id>`, reusing `scripts/lib/spec_discovery.py` rather than a new parser.
- [ ] 1.4 Implement evidence verification by invoking `scripts/evidence-validate.py` and requiring exit `0` plus a passing record for every test named in the row.
- [ ] 1.5 Implement whole-spec terminality: derive requirements from `<!-- id: ... -->` markers and reject a terminal status while any requirement is non-terminal.
- [ ] 1.6 Freeze exit codes `0` pass, `1` violation, `2` usage/config error, `3` nothing scanned, and make a zero-spec scan a failure rather than a green pass.
- [ ] 1.7 Write `scripts/spec-state-validate-negative-control.sh` covering seven cases: cell without row, row without cell, identical bounding commits, non-ancestor landing commit, empty marker intersection, invalid evidence bundle, and partial-closure terminal status.
- [ ] 1.8 Prove each control case is rejected for the designed reason and record the observed message per case as gate evidence.

## Gate 2 — The index becomes generated (blocking)

**Sprint:** S-L2 | **Effort:** M | **Priority:** P0
**Entry criteria:** Gate 1 exited and green on the real tree.
**Exit criteria:** `scripts/spec_index.py` renders `openspec/INDEX.md` from the
ledger plus closure tables, reproducing the current `31 specs` count and the
`CLOSED / PARTIAL / OPEN / UNKNOWN` rollup; a `--check` mode regenerates to a
temp path and exits non-zero on drift. The header claim "**Generated, not
typed**" becomes true, or is corrected to match the generator's actual
derivation.
**Dependencies:** S-L1.
**Stop conditions:** Generator output differs from the committed file for
rendering reasons rather than data → resolve before wiring `--check`, or the
gate cannot distinguish regression from reformat.

- [ ] 2.1 Implement `scripts/spec_index.py` rendering status from ledger rows and closure tables, reproducing today's counts exactly.
- [ ] 2.2 Add `--check` mode that regenerates to a temporary path and exits non-zero when the committed `openspec/INDEX.md` differs.
- [ ] 2.3 Verify the generator reproduces the current `31 specs` count and rollup on an unmodified tree before any ledger rows exist.
- [ ] 2.4 Reconcile the "Generated, not typed" header with the actual derivation, or correct the header text.

## Gate 3 — Enforcement placement (blocking, owner decision)

**Sprint:** S-L3 | **Effort:** M | **Priority:** P0
**Entry criteria:** Gate 1 exited; owner has chosen a placement.
**Exit criteria:** The `design.md` section 8 open decision is recorded as one
of: pre-commit hook (`core.hooksPath`), push-time CI on `main`, or both with the
audit-trail role documented. If pre-commit: a hook invoking the gate on staged
spec and ledger paths, plus documentation that `--no-verify` bypasses it and CI
is the backstop. If CI: a workflow whose failure is described as
detection-after-the-fact, never as prevention.
**Dependencies:** S-L1.
**Stop conditions:** Claiming a transition is "blocked" when the chosen
placement cannot block it → stop and restate the claim.

- [ ] 3.1 Record the owner's enforcement decision in `design.md` section 8: pre-commit, push-time CI, or both.
- [ ] 3.2 If pre-commit: add the hook invoking `spec_state_gate.py` on staged `openspec/` paths and document `--no-verify` bypass plus the CI backstop.
- [ ] 3.3 If CI: add the workflow and word its failure as detection-after-the-fact, given that `main` accepts direct pushes with no pull-request gate.
- [ ] 3.4 Audit every document for enforcement claims that exceed what the wired mechanism can do, and restate them.

## Gate 4 — Migration of existing specs (non-terminal until complete)

**Sprint:** S-L4 | **Effort:** L | **Priority:** P1
**Entry criteria:** Gates 1–3 exited.
**Exit criteria:** A report-only pass runs across all 31 specs and emits a
candidate row per `EXERCISED` cell. A candidate is accepted only when the cited
implementation path exists at `HEAD`, a `// spec: <id>` marker exists in a file
that changed within a resolvable window, and both commits resolve in reachable
history. `doc-truth` derives a real row from `0a26e37a`
(`docs(openspec): closure bookkeeping per owner dispositions 2026-10-13`).
`zig-opengl-engine`'s `4b69262` citation does not resolve in the full clone and
lands `UNPROVEN`. Every remaining unprovable cell records an explicit
`UNPROVEN` marker visible in the index. Unsupported-format specs yield "0
requirement IDs in the supported format", never "nothing to check".
**Dependencies:** S-L1, S-L2, S-L3.
**Stop conditions:** Any candidate accepted on a citation that does not resolve
→ stop and remove the row. Backfilling wrongly is worse than leaving blank.

- [ ] 4.1 Run the report-only backfill across all 31 specs and emit candidate rows with their supporting citations.
- [ ] 4.2 Apply the acceptance standard per candidate: implementation path exists at `HEAD`, marker present in a file that changed within a resolvable window, both commits resolvable.
- [ ] 4.3 Land `doc-truth` as the worked example, deriving its row from `0a26e37a` and confirming that commit resolves in reachable history.
- [ ] 4.4 Record `zig-opengl-engine`'s `4b69262` citation as `UNPROVEN` because it does not resolve in the full clone, and leave the spec non-terminal.
- [ ] 4.5 Mark every remaining unprovable cell `UNPROVEN` in a way that is visible in the index and cannot be promoted to proof by editing the spec.
- [ ] 4.6 Enable the ratchet: a spec with a ledger row cannot revert to free-text `Status:` authority, and removing a row requires a new row recording the correction.

## Deferred, explicitly not in this package

- Semantic verification that a landed change implements the requirement. The
  gate raises the floor to "code changed at the declared location"; static
  analysis cannot close the rest, and the evidence bundle has to carry the claim.
- Applying this gate to other repositories that carry `openspec/`. Scope is an
  open question in the proposal and is not assumed here.
- Bootstrapping: no ledger row may cite this change's own introduction commit as
  its landing commit.
