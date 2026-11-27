# Sprint plan — DG-04 archive task reconciliation

**Scope:** disposition historical task evidence without rewriting archives or treating old checkboxes as proof.
Tasks 1.1–1.2 and the first bounded source batch are recorded; the full 111-row task 2.1 review is not complete.

## Sequence

### S1 — intake/baseline

- Preserve the 58-archive, 907-row ready-tree inventory (797 checked, 110 unchecked, one `[~]`) and 64 archived delta directories/58 names.
- Confirm `task-2.1-batch-001.md` is the accepted bounded slice for ARC-TASK-001/002, not completion of task 2.1.

### S2 — implementation or evidence collection

- Continue task 2.1 through the remaining 109 entries in stable roster order, completing the 111-entry inventory by reviewing each unchecked task and vanished delta against current code, tests, CI, docs, and commit history.
- Record exact source/test/run references or explicit absence; preserve `[~]` as partial unless its missing pilot evidence is supplied. Do not reinterpret historical ticks.
- For task 2.2, carry only confirmed live work into a successor change with a new ID and accountable owner; first verify the archived files remain byte-for-byte unchanged.

### S3 — independent qualification

- A separate audit session checks the complete roster, every mapping/disposition, the delta capability comparison, and the archive immutability proof.
- Under task 2.3 rerun pinned `openspec validate --archived --strict --json`; verify the ten baseline archive-task failures have explicit dispositions and no task is called implemented solely from its checkbox.
- Stop any successor assignment without an owner, current evidence, or confirmed live work; retain unresolved historical entries as unresolved.

### S4 — integration/closeout

- Lead reconciles audit findings, verifies new task IDs and owner routes, repeats the archive validation and diff checks, then signs off the reconciliation artifact.
- The historical package remains unchanged; closure belongs to the reconciliation outcome, not edits to archived tasks.

## Bounded roles

- Lead: select/review batch boundaries and sign off. Luna: collect source-line-ordered evidence and produce disposition rows.
- A distinct audit session checks original bytes and evidence claims independently; owner input is requested only for genuinely owner-dependent dispositions.

## Sources

- [Proposal](proposal.md) · [Tasks](tasks.md) · [Baseline/current evidence](current-source-evidence.md)
- [First evidence batch](task-2.1-batch-001.md) · [Unchecked task roster](unchecked-task-roster.md) · [Global sprint plan](../../SPRINTS.md)

Use the package’s native acceptance path. If the session interface changes, assign its carrier-specific work through the [five-adapter matrix](../../SPRINTS.md#session-adapter-matrix).
