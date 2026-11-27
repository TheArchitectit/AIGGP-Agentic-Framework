# Tasks

## 1. Reconciliation roster

- [x] 1.1 Extract all 182 unproven rows with spec/requirement IDs; verify exact one-to-one roster mapping and record a stable input digest.
- [ ] 1.2 For every row, inspect enforcement site, behavioral tests, reachable ordered commits, and evidence validator result; record each proof conjunct and concrete missing evidence. The [candidate review](task-1.2-evidence.md) records provenance and discovery for all 182 rows. The [first](batches/batch-001/README.md), [second](batches/batch-002/README.md) and [third](batches/batch-003/README.md) sealed review batches cover rows 001–036. Another 146 await detailed review. Unsupported rows and outstanding proof remain open.

## 2. Sealed disposition

- [ ] 2.1 Produce a separate row-by-row JSONL disposition and seal it with the existing evidence pipeline; verify the validator accepts the aggregate report and each referenced bundle.
- [ ] 2.2 Keep unsupported rows UNPROVEN; for qualified rows prepare append-only ledger transitions with matching closure edits; verify no prose or marker alone promoted a row.
- [ ] 2.3 Run `scripts/spec_state_gate.py` and the index check over the reconciliation range; verify the original input roster and ledger are unchanged and all new transitions have valid proof.
- [ ] 2.4 Independently review the sealed disposition; verify every one of the 182 input rows appears exactly once and its decision matches the cited evidence.
