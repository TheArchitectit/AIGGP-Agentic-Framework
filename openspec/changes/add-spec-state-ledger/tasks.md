# Tasks: Bind Spec State Transitions to Commits and Evidence

Status is per-task below, not a blanket label. Gate 0 and Gate 1 are complete
and ticked with named evidence (2026-11-13); Gates 2-4 are still open, so no
existing spec has been reclassified and no ledger row exists yet.

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
`landed_commit`, `tests`, `evidence`, `evidence_digest`, `at`); the `to`
vocabulary is confirmed as exactly `EXERCISED | WIRED | ABSENT | NOT_RUN |
DIFFERS`, matching the existing cells; an empty `openspec/state-ledger.jsonl`
exists with a one-line schema comment so the diff base always resolves.
`evidence_digest` was added during Gate 0 (`design.md` section 1.1): the
validator requires `--expected` and a manifest cannot vouch for itself, so the
row is the only non-circular anchor.
**Dependencies:** None (first gate; must complete before S-L1-S-L4).
**Stop conditions:** Any state value invented beyond the frozen five → reject
and re-freeze. Any field that stores a timestamp used for ordering → reject;
commit ancestry is the only ordering source.

- [x] 0.1 Freeze the `openspec/state-ledger.jsonl` row schema `v1` in `design.md` section 1: exact field set, required versus optional, and the rejection rule for unknown fields. **Evidence:** `design.md:48-64` (field table), `design.md:66-69` (unknown fields rejected, not ignored); enforced by `scripts/spec_state_gate.py:172` (`validate_row`) and proven by the control's `unknown-field` case, which rejects `reviewed_by` with "unknown field(s) ['reviewed_by'] - schema v1 is frozen".
- [x] 0.2 Confirm the transition vocabulary is exactly the five existing cell values and record that no new state word is added by this change. **Evidence:** `design.md:70-72`; the gate's `STATES` tuple is exactly those five (`scripts/spec_state_gate.py:52`) and `from` admits `OPEN` only (`:189-191`). Measured at HEAD: 115 closure cells, all `EXERCISED`, zero cells outside the five.
- [x] 0.3 Add an empty `openspec/state-ledger.jsonl` with a one-line schema comment so every diff has a resolvable base for the ledger file itself. **Evidence:** `openspec/state-ledger.jsonl` carries the `devgate.spec-state-ledger/v1` tag, a pointer to `design.md` section 1.1, and the comment/blank-line rule; the gate skips `#` and blank lines (`scripts/spec_state_gate.py:147`).
- [x] 0.4 Record that `at` is informational only and MUST NOT be used for ordering; ancestry is the sole ordering source. **Evidence:** `design.md:74-80`; the gate type-checks `at` as a non-empty string and reads it nowhere else - ordering comes from `git merge-base --is-ancestor` (`scripts/spec_state_gate.py:87`, `:270-281`).

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
`scripts/specs-validate-negative-control.sh`) stages the seven forged cases and
requires rejection naming the designed defect for each, plus three guards:
zero-spec scan (exit 3), unresolvable revision (exit 2), and a row field outside
schema `v1`.
**Dependencies:** S-L0.
**Stop conditions:** Any control case passing → stop; the gate is not a gate. A
gate that cannot reject a forged closure MUST NOT ship as blocking.

- [x] 1.1 Implement diff-derived transition detection: compute changed requirements by diffing the spec tree between a base revision and `HEAD`, and reconcile that set against ledger rows added in the same range. **Evidence:** `scripts/spec_state_gate.py:122` (`tree_states`), `:263` (`reconcile`); both directions fail - a changed requirement with no row prints "a transition without authority", an added row with no state edit prints "a row with no state edit" (control cases `cell-no-row`, `row-no-cell`).
- [x] 1.2 Implement bounding-commit verification: both commits resolve, `opened_commit` is a strict ancestor of `landed_commit`, `landed_commit` is an ancestor of `HEAD`, and the two are distinct. **Evidence:** `scripts/spec_state_gate.py:82` (`rev_resolves`), `:87` (`is_ancestor`), `:270-281`; control cases `same-commits` ("a transition must span two commits") and `non-ancestor` ("is not an ancestor of").
- [x] 1.3 Implement the marked-source check: the `opened_commit..landed_commit` diff must touch a file carrying `// spec: <req-id>` or `# spec: <req-id>`, reusing `scripts/lib/spec_discovery.py` rather than a new parser. **Evidence:** `scripts/spec_state_gate.py:209` (`marked_source`) imports `MARKER`/`ID` from `scripts/lib/spec_discovery.py:38-39`; control case `no-marker` ("carries 'spec: demo-01'").
- [x] 1.4 Implement evidence verification by invoking `scripts/evidence-validate.py` and requiring exit `0` plus a passing record for every test named in the row. **Evidence:** `scripts/spec_state_gate.py:229` (`evidence_problem`) passes the row's `evidence_digest` as `--expected`; the bundle's `tests.json` must be a sealed manifest object and each named test must read exactly `passed` (`design.md:151-175`). Control cases `bad-digest` (validator exit 1) and `skipped-test` ("not 'passed'").
- [x] 1.5 Implement whole-spec terminality: derive requirements from `<!-- id: ... -->` markers and reject a terminal status while any requirement is non-terminal. **Evidence:** `scripts/spec_state_gate.py:122` derives the requirement set from markers via `spec_discovery._requirement_blocks` (drafts excluded per SGA-02), `:296-305` rejects `Status: CLOSED` with a non-terminal cell; a spec with zero requirement IDs is reported as unsupported format (`:270-276`). Control case `partial-closure` (`CLOSED` while `demo-02` is `WIRED`).
- [x] 1.6 Freeze exit codes `0` pass, `1` violation, `2` usage/config error, `3` nothing scanned, and make a zero-spec scan a failure rather than a green pass. **Evidence:** `scripts/spec_state_gate.py:50` defines the four codes; `:331-337` maps them. Control cases `empty-scan` (zero specs → 3) and `bad-revision` (unresolvable base → 2).
- [x] 1.7 Write `scripts/spec-state-validate-negative-control.sh` covering seven cases: cell without row, row without cell, identical bounding commits, non-ancestor landing commit, empty marker intersection, invalid evidence bundle, and partial-closure terminal status. **Evidence:** `scripts/spec-state-validate-negative-control.sh` stages each case in a `mktemp -d` fixture and asserts the gate's own message; run of 2026-11-13 output is recorded under 1.8. Two extra cases beyond the seven: `empty-scan` (exit 3) and `unknown-field` (Gate 0.1's rejection rule).
- [x] 1.8 Prove each control case is rejected for the designed reason and record the observed message per case as gate evidence. **Evidence:** `./scripts/spec-state-validate-negative-control.sh` exit 0, every case `ok`, 2026-11-13:
  - positive control: exit 0, "work..case-valid reconciled (1 commit(s))"
  - cell-no-row: "demo/demo-01: state changed between work and case-cell-no with no ledger row - a transition without authority"
  - row-no-cell: "row 0: ledger adds demo/demo-01 -> EXERCISED but the spec's state did not change ... - a row with no state edit"
  - same-commits: "opened_commit equals landed_commit (58cebc28ec88) - a transition must span two commits"
  - non-ancestor: "landed_commit 91ea052cc5d2 is not an ancestor of case-non-anc"
  - no-marker: "no file changed in ffda19138b67..b79946d50de7 carries 'spec: demo-01' and still exists at HEAD"
  - bad-digest: "evidence-validate.py rejected 'evidence/bundle' (exit 1): INVALID - bundle fails digest verification"
  - skipped-test: "records test 'tests/test_demo.py::test_alpha' as 'skipped', not 'passed'"
  - partial-closure: "Status line says terminal ('CLOSED (EXERCISED 2)') while 1 requirement(s) are not EXERCISED: ['demo-02']"
  - empty-scan: exit 3, "empty scan is a failure"
  - bad-revision: exit 2, "does not resolve to a commit"
  - unknown-field: "unknown field(s) ['reviewed_by'] - schema v1 is frozen"

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

- [x] 2.1 Implement `scripts/spec_index.py` rendering status from ledger rows and closure tables, reproducing today's counts exactly. **Evidence:** `scripts/spec_index.py` (`read_spec`, `classify`, `render`); a requirement with no closure cell takes its latest ledger row's recorded state, cells decide status when present, the owner's `DEFERRED` decision outranks both.
- [x] 2.2 Add `--check` mode that regenerates to a temporary path and exits non-zero when the committed `openspec/INDEX.md` differs. **Evidence:** `python3 scripts/spec_index.py --check` prints "OK - INDEX.md matches the generator" (exit 0); the drift path writes the generated text to a `NamedTemporaryFile` and prints a unified diff before exiting 1. Wired into CI as "Index is generated (spec-state-07)" (`.github/workflows/ci.yml`, specs job).
- [x] 2.3 Verify the generator reproduces the current `31 specs` count and rollup on an unmodified tree before any ledger rows exist. **Evidence:** rollup reproduced exactly: `**44 specs** - CLOSED 43 · DEFERRED 1 · PARTIAL 0 · OPEN 0 · UNKNOWN 0`, identical to the committed line. **Deviation recorded:** this package was written against `7d3ebc5`, where 31 specs existed; the tree now holds 44, so "31" was stale in the exit criteria and the generator was verified against 44. Two title cells changed during verification: `fleet-manager-plan` and `fleet-manager-extraction` carried curated titles in `INDEX.md` that their specs did not, so the spec headings were corrected to the curated titles rather than the index losing them. The DEFERRED row's hand-written evidence prose became `Status: DEFERRED`; the rationale it carried is stated in the index header and in the spec itself.
- [x] 2.4 Reconcile the "Generated, not typed" header with the actual derivation, or correct the header text. **Evidence:** the header is now emitted by the generator (`HEADER` in `scripts/spec_index.py`) and `--check` fails on any divergence, so the claim is true by construction rather than asserted. The header wording was kept because it now describes reality; the file's only data change in this gate is the DEFERRED evidence cell.

## Gate 3 — Enforcement placement (blocking, owner decision)

**Status 2026-11-13: BLOCKED on the owner.** Gates 0-2 exited; the gate, its
control, and the generator exist and are green on the real tree. Placement is
the one question the implementation cannot answer for the owner, and this
package's global stop rule freezes Gate 4 behind it. The three placements and
their honest claims are in `design.md` section 8; the recommendation there is
pre-commit as the block plus push-time CI as the audit trail, with CI described
as detection, never prevention.

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
