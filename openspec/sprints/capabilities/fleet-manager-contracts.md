# fleet-manager-contracts sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **fleet manager maintainer and the operator for any live lane**. Bring disposable fleet records or a boundary package with declared inputs to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept package behavior and any separate operator-owned claim. |
| S2. Luna writer | Compare both producer/consumer directions in an extracted package. Reproduce the unsupported required-reason gap and qualify the corrected suite against both fixture changes. Start at [fleet-manager/tests/test_contracts_v1.py](../../../fleet-manager/tests/test_contracts_v1.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for package behavior and any separate operator-owned claim. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`repo-003-01`](../../specs/fleet-manager-contracts/spec.md#requirement-cross-boundary-documents-are-versioned-and-declared) Cross-boundary documents are versioned and declared | a field nobody declared crosses the boundary / a document carries no version / a shape change is needed |
| [`repo-003-02`](../../specs/fleet-manager-contracts/spec.md#requirement-a-consumer-refuses-versions-it-does-not-implement) A consumer refuses versions it does not implement | a future major arrives / the version is a string |
| [`repo-004-01`](../../specs/fleet-manager-contracts/spec.md#requirement-contract-tests-run-in-both-directions) Contract tests run in both directions | the other side's document is malformed / the core side's minimum changes |
| [`repo-004-02`](../../specs/fleet-manager-contracts/spec.md#requirement-a-producer-cannot-emit-a-document-its-contract-rejects) A producer cannot emit a document its contract rejects | a builder is asked for an inconsistent decision |
| [`repo-004-03`](../../specs/fleet-manager-contracts/spec.md#requirement-decisions-and-receipts-carry-what-makes-them-actionable) Decisions and receipts carry what makes them actionable | a refusal arrives with no reason / a completion is claimed without evidence / a tier field is introduced |
| [`repo-004-04`](../../specs/fleet-manager-contracts/spec.md#requirement-the-boundarys-open-core-import-surface-is-pinned) The boundary's open-core import surface is pinned | a second core module is imported |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-134, DG02-U-135, DG02-U-136, DG02-U-137, DG02-U-138, DG02-U-139. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [qualify-dg02-boundary-contract-domain-gaps](../../changes/qualify-dg02-boundary-contract-domain-gaps/sprint-plan.md).

[Published specification](../../specs/fleet-manager-contracts/spec.md) and [sprint dispatch](../../SPRINTS.md).
