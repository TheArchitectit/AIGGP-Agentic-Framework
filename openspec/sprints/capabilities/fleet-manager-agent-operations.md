# fleet-manager-agent-operations sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **fleet manager maintainer and the operator for any live lane**. Bring disposable fleet records or a boundary package with declared inputs to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept package behavior and any separate operator-owned claim. |
| S2. Luna writer | Exercise typed operations, allowed capabilities and evidence-bearing receipts. Inspect parameter-name refusal ordering and distinguish in-memory ledger results from persistent proof. Start at [fleet-manager/tests/test_operations_v1.py](../../../fleet-manager/tests/test_operations_v1.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for package behavior and any separate operator-owned claim. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`fleet-005-01`](../../specs/fleet-manager-agent-operations/spec.md#requirement-an-operation-is-a-typed-instruction-and-cannot-carry-a-command) An operation is a typed instruction and cannot carry a command | a shell-shaped parameter name is offered / a parameter that is not of this kind / a required parameter is missing |
| [`fleet-005-02`](../../specs/fleet-manager-agent-operations/spec.md#requirement-an-agent-may-only-be-given-work-it-declared) An agent may only be given work it declared | work the agent never declared / cancellation without the policy |
| [`fleet-005-03`](../../specs/fleet-manager-agent-operations/spec.md#requirement-parameters-and-receipts-carry-references-never-secrets) Parameters and receipts carry references, never secrets | a token pasted into a parameter / registration material instead of a reference |
| [`fleet-005-04`](../../specs/fleet-manager-agent-operations/spec.md#requirement-a-receipt-is-evidence-tied-to-issued-work) A receipt is evidence tied to issued work | a read-only operation has no receipt / a receipt for work that was never issued / a completion with nothing to show / a second, different answer |
| [`fleet-005-05`](../../specs/fleet-manager-agent-operations/spec.md#requirement-the-authoritative-receipt-is-built-not-forwarded) The authoritative receipt is built, not forwarded | the mapping drifts from the contract / the enrollment script grows an option / an agent claim reaches the evidence plane |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-125, DG02-U-126, DG02-U-127, DG02-U-128, DG02-U-129. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [qualify-dg02-agent-operations-boundary-gaps](../../changes/qualify-dg02-agent-operations-boundary-gaps/sprint-plan.md).

[Published specification](../../specs/fleet-manager-agent-operations/spec.md) and [sprint dispatch](../../SPRINTS.md).
