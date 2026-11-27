# adoption-and-policy sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **consumer integration owner**. Bring a synthetic consumer, a pinned result and a trusted decision point to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept consumer acceptance over the selected subject and policy. |
| S2. Luna writer | Compare advisory and mandatory decisions against one signed policy revision. Retain the exception scope and expiry with the decision that consumed them. Start at [tests/test_hub_coherence_adoption_policy.py](../../../tests/test_hub_coherence_adoption_policy.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for consumer acceptance over the selected subject and policy. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`coh-pol-01`](../../specs/adoption-and-policy/spec.md#requirement-centrally-enforced-minimums) centrally enforced minimums | lower severity locally / trusted-but-obsolete central policy |
| [`coh-pol-02`](../../specs/adoption-and-policy/spec.md#requirement-authenticated-policy-authority) authenticated policy authority | forged approval / policy substitution attempt |
| [`coh-pol-03`](../../specs/adoption-and-policy/spec.md#requirement-bounded-advisory-stage) bounded advisory stage | advisory expiry |
| [`coh-pol-04`](../../specs/adoption-and-policy/spec.md#requirement-no-regression-ratchet) no-regression ratchet | four existing and one new violation / one fixed, one new, count unchanged |
| [`coh-pol-05`](../../specs/adoption-and-policy/spec.md#requirement-finding-fingerprint-definition) finding fingerprint definition | severity escalation of baseline debt / recurrence after remediation |
| [`coh-pol-06`](../../specs/adoption-and-policy/spec.md#requirement-scoped-exceptions) scoped exceptions | wildcard exception / exception never rewrites outcome |
| [`coh-pol-07`](../../specs/adoption-and-policy/spec.md#requirement-enforcement-boundary-is-external) enforcement boundary is external | workflow deleted / result from another candidate |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-002, DG02-U-003, DG02-U-004, DG02-U-005, DG02-U-006, DG02-U-007, DG02-U-008. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [define-consumer-evidence-boundary](../../changes/define-consumer-evidence-boundary/sprint-plan.md).

[Published specification](../../specs/adoption-and-policy/spec.md) and [sprint dispatch](../../SPRINTS.md).
