# Sprint plan — DG-02 evidence ledger reconciliation

**Scope:** complete task 1.2 for the remaining rows, then finish the sealed disposition flow.
Rows 001–144 have 12 reviewed batches; batch-012 covers 133–144 and leaves every row UNPROVEN. The next row is DG02-U-145; remaining range is 145–182.

## Sequence

### S1 — intake/baseline

- Preserve the pinned roster/input digest and immutable source ledger; verify batch-012’s manifest/receipt before using it as history.
- Reconcile rows 145–182 in four bounded slices: 145–156, 157–168, 169–180, and 181–182. Each is discovery, not automatic acceptance.

### S2 — implementation or evidence collection

- For each remaining row under task 1.2, inspect the owning requirement, enforcement path, behavior tests, reachable ordered history, and exact evidence-validator result; record every conjunct and gap.
- Keep findings row-bound; use NOT_RUN for absent test, bundle, or lifecycle evidence. Do not infer behavior from a source marker or test name.
- Under 2.1 prepare one JSONL disposition for all 182 IDs, seal it through the existing evidence pipeline, and validate the aggregate plus every referenced bundle.

### S3 — independent qualification

- A separate audit session checks one-to-one roster coverage, row/source digests, commit order/change overlap, test identity, bundle digest, and each proposed verdict.
- Under 2.2, create append-only transitions and closure edits only where all proof conditions pass. Unsupported rows remain UNPROVEN.
- Resolve duplicate or missing roster entries before sealing. Keep rows with unresolved provenance or a mismatched bundle UNPROVEN, record the reason and continue reviewing the remaining rows.

### S4 — integration/closeout

- Under 2.3 run the state gate and generated index check over the reviewed range; prove the original roster and ledger bytes are unchanged.
- Under 2.4 lead reconciles the independent audit, reruns required gates at the candidate revision, and signs off only the accepted disposition.

## Bounded roles

- Lead: own selection, disposition policy, review reconciliation, final gates, and sign-off. Luna: collect row evidence and prepare bounded slices with exact identities and digests.
- A distinct audit session recomputes every row finding, the receipt digest and the complete batch seal. The lead independently verifies every row before sign-off. No writer audits its own batch.

## Sources

- [Proposal](proposal.md) · [Tasks](tasks.md) · [Input manifest and roster evidence](roster-evidence.md)
- [Task 1.2 discovery](task-1.2-evidence.md) · [Batch 012](batches/batch-012/README.md) · [Global sprint plan](../../SPRINTS.md)

Use the package’s native acceptance path. If the session interface changes, assign its carrier-specific work through the [five-adapter matrix](../../SPRINTS.md#session-adapter-matrix).
