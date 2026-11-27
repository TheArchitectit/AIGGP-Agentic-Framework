# game-type-phase-matrix sprint plan

At `cb2205c` the index recorded **DEFERRED**. Hold implementation until the consuming game owner elects to proceed. The upstream team can prepare or review the handoff.

Route acceptance to the **consuming game owner**. Bring an explicit adoption decision in the consuming game repository to intake.

**Session adapters.** The five session adapters become relevant only if the game owner activates the phase policy. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Obtain the consuming owner's decision and candidate revision first. Map the requirement IDs below to their source and establish who can accept the consumer-owned implementation and its original evidence. |
| S2. Luna writer | If the owner activates the work, collect its implementation and receipts. Start at [scripts/game-framework-README.md](../../../scripts/game-framework-README.md). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for the consumer-owned implementation and its original evidence. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`game-matrix-01`](../../specs/game-type-phase-matrix/spec.md#requirement-manifest-driven-phase-gate-planned) Manifest-driven phase gate (planned) | unknown game type fails closed / no false enforcement claim today |
| [`game-matrix-02`](../../specs/game-type-phase-matrix/spec.md#requirement-phase-gating-follows-the-matrix-row-planned--not-implemented) Phase gating follows the matrix row (planned — NOT IMPLEMENTED) | phase ahead of its gates |
| [`game-matrix-03`](../../specs/game-type-phase-matrix/spec.md#requirement-unknown-game-types-fail-closed-planned--not-implemented) Unknown game types fail closed (planned — NOT IMPLEMENTED) | invented type |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

[Published specification](../../specs/game-type-phase-matrix/spec.md) and [sprint dispatch](../../SPRINTS.md).
