# fleet-manager-extraction sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **fleet manager maintainer and the operator for any live lane**. Bring disposable fleet records or a boundary package with declared inputs to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept package behavior and any separate operator-owned claim. |
| S2. Luna writer | Rehearse the package with only declared build inputs, then collect open-core tests with the package absent. Retain both phase results and dependency inventories. Start at [fleet-manager/scripts/extraction_rehearsal.py](../../../fleet-manager/scripts/extraction_rehearsal.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for package behavior and any separate operator-owned claim. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`repo-005-01`](../../specs/fleet-manager-extraction/spec.md#requirement-the-boundary-package-builds-and-tests-from-declared-inputs-alone) The boundary package builds and tests from declared inputs alone | a hidden repository-relative import |
| [`repo-005-02`](../../specs/fleet-manager-extraction/spec.md#requirement-the-open-core-builds-and-tests-with-the-boundary-absent) The open core builds and tests with the boundary absent | a core module starts depending on the boundary / collection finds nothing |
| [`repo-005-03`](../../specs/fleet-manager-extraction/spec.md#requirement-files-allowed-to-name-the-boundary-are-declared-and-pinned) Files allowed to name the boundary are declared and pinned | CI runs the boundary's own suite / a core module names the boundary / the allowance is declared for a file inside the boundary |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-145, DG02-U-146, DG02-U-147. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md). The missing-Node rehearsal control and its explicit scan skip are tracked in [the active extraction/lifecycle/planning qualification](../../changes/qualify-dg02-extraction-lifecycle-plan-gaps/sprint-plan.md).

[Published specification](../../specs/fleet-manager-extraction/spec.md) and [sprint dispatch](../../SPRINTS.md).
