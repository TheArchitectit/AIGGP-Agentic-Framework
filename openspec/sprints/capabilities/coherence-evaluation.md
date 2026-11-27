# coherence-evaluation sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **coherence service maintainer**. Bring pinned context, subject, policy and evaluator artifacts to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept the subject identity, decision and sealed evidence. |
| S2. Luna writer | Evaluate a declared assertion set twice against frozen inputs. Reconcile every required assertion, including any unavailable result, to the output ledger. Start at [tests/test_hub_coherence_runtime.py](../../../tests/test_hub_coherence_runtime.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for the subject identity, decision and sealed evidence. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`coh-eval-01`](../../specs/coherence-evaluation/spec.md#requirement-deterministic-evaluation) deterministic evaluation | repeated execution / evaluator reads time |
| [`coh-eval-02`](../../specs/coherence-evaluation/spec.md#requirement-complete-required-assertion-execution) complete required assertion execution | plugin crash / repository attempts to skip assertion / dependency-blocked assertion |
| [`coh-eval-03`](../../specs/coherence-evaluation/spec.md#requirement-assertion-results-ledger) assertion results ledger | ledger accounting / assertion with no findings |
| [`coh-eval-04`](../../specs/coherence-evaluation/spec.md#requirement-semantic-assertion-traceability) semantic assertion traceability | orphan requirement / assertion without requirement |
| [`coh-eval-05`](../../specs/coherence-evaluation/spec.md#requirement-underlying-truth-is-preserved) underlying truth is preserved | advisory violation |
| [`coh-eval-06`](../../specs/coherence-evaluation/spec.md#requirement-evaluators-execute-only-declared-inputs) evaluators execute only declared inputs | undeclared path access |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-026, DG02-U-027, DG02-U-028, DG02-U-029, DG02-U-030, DG02-U-031. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [define-consumer-evidence-boundary](../../changes/define-consumer-evidence-boundary/sprint-plan.md).

[Published specification](../../specs/coherence-evaluation/spec.md) and [sprint dispatch](../../SPRINTS.md).
