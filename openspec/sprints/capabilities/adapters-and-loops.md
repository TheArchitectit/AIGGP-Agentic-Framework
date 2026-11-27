# adapters-and-loops sprint plan

At `cb2205c` the index recorded **UNKNOWN**. Start by locating the implementation and a measurable entry point. Record missing or externally held evidence before selecting an implementation change.

Route acceptance to the **consumer integration owner**. Bring a synthetic consumer, a pinned result and a trusted decision point to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept consumer acceptance over the selected subject and policy. |
| S2. Luna writer | Use an external-tool result and two subject revisions. Preserve the emitting tool's identity and require a fresh verdict after the loop changes the subject. Start at [tests/test_hub_coherence_adoption_policy.py](../../../tests/test_hub_coherence_adoption_policy.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for consumer acceptance over the selected subject and policy. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`adapter-01`](../../specs/adapters-and-loops/spec.md#requirement-identity-preserving-ingestion) identity-preserving ingestion | adapter output |
| [`adapter-02`](../../specs/adapters-and-loops/spec.md#requirement-agent-loop-verdict-contract) agent-loop verdict contract | loop self-certification attempt |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

Coordinate overlapping work with [define-consumer-evidence-boundary](../../changes/define-consumer-evidence-boundary/sprint-plan.md).

[Published specification](../../specs/adapters-and-loops/spec.md) and [sprint dispatch](../../SPRINTS.md).
