# Tasks: Six Open-Item Gates, One per Deficiency Family

Status is per-task below, not a blanket label. Every gate in this package is
implemented and runnable; **none is wired into CI**, because placement is an
owner decision (see the closing section).

## 1. Specification

- [x] 1.1 `branch-drift` delta with four requirements (`bd-01..04`).
- [x] 1.2 `evidence-claims` delta with six requirements (`evc-01..06`).
- [x] 1.3 `open-item-aging` delta with four requirements (`oia-01..04`).
- [x] 1.4 `secret-rotation` delta with four requirements (`sr-01..04`).
- [x] 1.5 `surface-reach` delta with four requirements (`srch-01..04`).
- [x] 1.6 `tree-clean` delta with four requirements (`tc-01..04`).
  Validated with the CI pin (`@fission-ai/openspec@1.14.3`,
  `validate --all --strict`); the negative control still refuses the planted
  malformed item.

## 2. Implementation — one script per family

- [x] 2.1 `scripts/branch_drift_check.py` — compares every local ref tip
  against advertised remote refs; an archived commit is a recorded decision,
  not drift.
- [x] 2.2 `scripts/evidence_claim_check.py` — parses `DEFERRED`, `MOCK`, and
  `STUB` markers in tracked source; exemptions come from a declared file
  (`--allow`), never from inference.
- [x] 2.3 `scripts/open_item_aging_check.py` — reads an append-only backlog and
  triage ledger; an aged item with no live disposition fails, named
  individually.
- [x] 2.4 `scripts/secret_rotation_check.py` — reads a rotation ledger; a
  detection removed from `HEAD` without a revocation (date + evidence) past the
  window fails.
- [x] 2.5 `scripts/surface_reach_check.py` — reads a surfaces manifest; every
  declared surface must exist and hold identical content.
- [x] 2.6 `scripts/tree_clean_check.py` — classifies working-tree entries into
  committed change, declared generated churn, file-mode-only churn, or real
  dirt; only the last fails by default.
- [x] 2.7 Every script keeps the shared nothing-scanned contract (exit `3`,
  never a bare green) and the frozen exit codes `0/1/2/3`; each takes explicit
  input paths and writes no state.
- [x] 2.8 Each script carries `// spec:` markers for its own family, and every
  file is executable in the index (shebang implies `100755`).
- [x] 2.9 Each gate was demonstrated failing on a fixture before the commit, and
  passing on a clean fixture.

## 3. Traceability

- [x] 3.1 `scripts/spec_traceability.py --ratchet` reports 228/241 covered; the
  floor is raised to 228 so removing a marker later is a failure.
- [x] 3.2 The nine `spec-state-*` IDs proposed by `add-spec-state-ledger` remain
  advisory (specification-only package, no enforcing code yet).

## 4. Open — not done by this change

- [ ] 4.1 Wire each gate where it can see its inputs. Placement is an owner
  decision: a push-time CI job **detects** a violation that already landed, and
  must not be described as blocking on a repository that accepts direct pushes
  to `main` (the same honesty rule as `spec-state-09`).
- [ ] 4.2 Adopt a triage ledger and a rotation ledger with content. The gates
  read these files; creating them is a process decision, and an empty ledger is
  a pass, not evidence.
- [ ] 4.3 Unit tests under `tests/` for each gate. Today the evidence is the
  authoring-time demonstration named in the commit; a suite that pins the
  passing and failing fixtures would make that evidence re-runnable.
