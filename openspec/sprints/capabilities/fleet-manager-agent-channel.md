# fleet-manager-agent-channel sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **fleet manager maintainer and the operator for any live lane**. Bring disposable fleet records or a boundary package with declared inputs to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept package behavior and any separate operator-owned claim. |
| S2. Luna writer | Qualify enrollment, signed report verification, sequence state and key rotation using synthetic identities. State which verifier and persistence boundary supplied each result. Start at [fleet-manager/tests/test_channel_v1.py](../../../fleet-manager/tests/test_channel_v1.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for package behavior and any separate operator-owned claim. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`fleet-004-01`](../../specs/fleet-manager-agent-channel/spec.md#requirement-the-manager-never-initiates-contact-with-a-host) The manager never initiates contact with a host | a network import is added / an agent calls in |
| [`fleet-004-02`](../../specs/fleet-manager-agent-channel/spec.md#requirement-enrollment-is-one-time-and-bound-a-key-belongs-to-one-host) Enrollment is one-time and bound; a key belongs to one host | a token is redeemed twice / a key is offered by a second host / a revoked key is offered again / a refusal for an unknown token |
| [`fleet-004-03`](../../specs/fleet-manager-agent-channel/spec.md#requirement-reports-are-signed-over-one-frozen-profile) Reports are signed over one frozen profile | a forged signature / the bytes change / the provider is unavailable |
| [`fleet-004-04`](../../specs/fleet-manager-agent-channel/spec.md#requirement-replay-protection-is-stateful-and-strict) Replay protection is stateful and strict | a captured report is replayed / a report is lost / a forged report arrives first / a nonce is reused under a new sequence |
| [`fleet-004-05`](../../specs/fleet-manager-agent-channel/spec.md#requirement-rotation-overlaps-for-a-bounded-window-revocation-is-immediate) Rotation overlaps for a bounded window; revocation is immediate | a report in flight during rotation / a report after the overlap / a revoked host / a credential outlives its absolute lifetime |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-120, DG02-U-121, DG02-U-122, DG02-U-123, DG02-U-124. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [qualify-dg02-agent-operations-boundary-gaps](../../changes/qualify-dg02-agent-operations-boundary-gaps/sprint-plan.md), [qualify-dg02-spec-3d-fleet-gaps](../../changes/qualify-dg02-spec-3d-fleet-gaps/sprint-plan.md).

[Published specification](../../specs/fleet-manager-agent-channel/spec.md) and [sprint dispatch](../../SPRINTS.md).
