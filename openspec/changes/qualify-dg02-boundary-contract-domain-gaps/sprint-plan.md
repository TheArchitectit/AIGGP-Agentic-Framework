# Sprint plan — DG-02 boundary, contracts, and domain gaps

Use the [sprint dispatch guide](../../SPRINTS.md) with this package’s [tasks](tasks.md), [proposal](proposal.md), and [batch 012 evidence](../dg-02-evidence-ledger-reconciliation/batches/batch-012/README.md).

Exercise the native entry point for this change. A change to session startup or manifest handling also needs a carrier-specific receipt. [Session adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Roles

- Lead: coordinate requirement mapping, review the implementation/evidence split, and sign off on state-gate proposals.
- Luna: collect defensive test evidence and assemble per-row evidence bundles.
- Independent auditor: separate session reviews commit provenance, behavior, manifests, and validator outcomes.
- Accountable owners: fleet boundary maintainer, contract producer/consumer owners, desired-state model owner, and DG-02 evidence maintainer.

## S1 — intake and baseline

- Use batch 012 as the review baseline for DG02-U-133–144; all rows remain UNPROVEN absent accepted provenance/bundles.
- Map tasks 1.1–1.5 to `repo-002-04`, `repo-003-01..02`, and `repo-004-01..04`; tasks 2.1–2.3 to `fleet-001-01..05`; task 2.4 to rows 133–144.
- Inventory current boundary CI receipt, contract suite and extracted build inputs, model tests, and source markers without inferring behavior from markers.
- Exit with a full row-to-task map, pinned baseline SHA, owners, and exact evidence still missing per row.

## S2 — implementation and evidence

- Tasks 1.1–1.3: capture clean/violation/unusable boundary exits, schema version diagnostics, consumer-required paths/reasons, and extracted-package behavior.
- Tasks 1.4–1.5: qualify request validation/echo, decisions, receipts, closed enums/no commercial fields, and undeclared core-import rejection.
- Tasks 2.1–2.3: bind immutable revision and observation separation, complete pool/secret diagnostics, host capacity/drain/rollout behaviors to existing tests and explicit controls.
- Task 2.4: recover reviewable implementation/test provenance and expected digest for each proposed transition; leave unsupported rows UNPROVEN.
- Exit with per-requirement test receipts and bundles; keep fixture evidence distinct from historical range proof.

## S3 — independent qualification

- Auditor checks task/test mapping, replays the behavioral tests and the new contract fixture controls, validates extracted inputs and negative controls, and independently verifies each evidence bundle.
- Auditor checks commit range order and changed-file overlap for markers/tests; reject source-only or QA-narrative-only proof.
- Lead reconciles findings and submits only evidence-complete transitions to the state gate.

## S4 — integration and closeout

- Run boundary and fleet suites, strict OpenSpec, traceability, evidence validation, and state gate at the final head.
- Handoff per row: source range, named behavioral results, bundle path/digest, validator receipt, state-gate result, and auditor verdict.
- Archive/close only if the independent review and gate accept; no task checkbox or ledger state is inferred from the batch review alone.
