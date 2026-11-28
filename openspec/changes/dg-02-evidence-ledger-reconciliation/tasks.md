# Tasks

## 1. Reconciliation roster

- [x] 1.1 Extract all 182 unproven rows with spec/requirement IDs; verify exact one-to-one roster mapping and record a stable input digest.
- [ ] 1.2 For every row, inspect the enforcement site, behavioral tests, reachable ordered commits and evidence validator result. Record each proof conjunct and the missing evidence. Initial discovery covers all 182 rows. Thirteen reviewed batches cover rows 001-156. All 182 remain UNPROVEN. The remaining 26 start at DG02-U-157. [Initial discovery](task-1.2-evidence.md) and [batch index](README.md).

## 2. Sealed disposition

- [ ] 2.1 Produce a separate row-by-row JSONL disposition and seal it with the existing evidence pipeline; verify the validator accepts the aggregate report and each referenced bundle.
- [ ] 2.2 Keep unsupported rows UNPROVEN; for qualified rows prepare append-only ledger transitions with matching closure edits; verify no prose or marker alone promoted a row.
- [ ] 2.3 Run `scripts/spec_state_gate.py` and the index check over the reconciliation range; verify the original input roster and ledger are unchanged and all new transitions have valid proof.
- [ ] 2.4 Independently review the sealed disposition; verify every one of the 182 input rows appears exactly once and its decision matches the cited evidence.
