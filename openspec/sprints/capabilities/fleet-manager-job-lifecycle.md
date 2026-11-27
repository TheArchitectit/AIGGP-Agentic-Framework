# fleet-manager-job-lifecycle sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **fleet manager maintainer and the operator for any live lane**. Bring disposable fleet records or a boundary package with declared inputs to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept package behavior and any separate operator-owned claim. |
| S2. Luna writer | Trace an instance from allocation through cleanup or quarantine. Verify a used instance cannot reenter the warm inventory and that replacement waits for the required receipt. Start at [fleet-manager/tests/test_lifecycle_v1.py](../../../fleet-manager/tests/test_lifecycle_v1.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for package behavior and any separate operator-owned claim. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`fleet-008-01`](../../specs/fleet-manager-job-lifecycle/spec.md#requirement-one-job-per-instance-and-no-way-back-to-warm) One job per instance, and no way back to warm | a second job is refused / the state machine is closed / a used instance is not warm / an uncertain disconnect is a terminal state / no transition back to warm |
| [`fleet-008-02`](../../specs/fleet-manager-job-lifecycle/spec.md#requirement-cleanup-is-proved-before-a-replacement-joins-capacity) Cleanup is proved before a replacement joins capacity | an incomplete proof is refused / a proof without a job identity / a failed disposal is not a proof / admission waits for the proof |
| [`fleet-008-03`](../../specs/fleet-manager-job-lifecycle/spec.md#requirement-quarantine-is-a-state-with-a-reason) Quarantine is a state with a reason | a failed proof quarantines / a quarantine is inspectable / quarantine is not deletion |
| [`fleet-008-04`](../../specs/fleet-manager-job-lifecycle/spec.md#requirement-resource-limits-are-required-and-rendered) Resource limits are required and rendered | a missing limit is refused / an unbounded limit is refused / the command carries the limits |
| [`fleet-008-05`](../../specs/fleet-manager-job-lifecycle/spec.md#requirement-lifecycle-failures-are-the-closed-typed-errors) Lifecycle failures are the closed typed errors | a refused offer is a policy denial / an incomplete cleanup is a cleanup failure / the kind matches the failure / an unexpected exception is classified |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-148, DG02-U-149, DG02-U-150, DG02-U-151, DG02-U-152. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

[Published specification](../../specs/fleet-manager-job-lifecycle/spec.md) and [sprint dispatch](../../SPRINTS.md).
