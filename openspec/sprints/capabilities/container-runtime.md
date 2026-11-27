# container-runtime sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **coherence service maintainer**. Bring pinned context, subject, policy and evaluator artifacts to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept the subject identity, decision and sealed evidence. |
| S2. Luna writer | Qualify a digest-pinned evaluator in its intended isolated runtime. Record the selected image, allowed inputs, writable outputs and bounded termination receipts. Start at [tests/test_hub_coherence_container_real.py](../../../tests/test_hub_coherence_container_real.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for the subject identity, decision and sealed evidence. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`coh-rt-01`](../../specs/container-runtime/spec.md#requirement-immutable-runtime) immutable runtime | tag-only image |
| [`coh-rt-02`](../../specs/container-runtime/spec.md#requirement-launcher-validated-isolation) launcher-validated isolation | runtime violates isolation requirements / self-report not trusted |
| [`coh-rt-03`](../../specs/container-runtime/spec.md#requirement-default-deny-network) default-deny network | approved external registry lookup / evaluator attempts direct egress |
| [`coh-rt-04`](../../specs/container-runtime/spec.md#requirement-least-privilege-secrets) least-privilege secrets | evaluator lacks the named secret capability / secret redaction |
| [`coh-rt-05`](../../specs/container-runtime/spec.md#requirement-bounded-execution) bounded execution | evaluator exhausts a configured limit / output overflow |
| [`coh-rt-06`](../../specs/container-runtime/spec.md#requirement-built-in-evaluators-for-the-initial-runtime) built-in evaluators for the initial runtime | repository supplies executable evaluator |
| [`coh-rt-07`](../../specs/container-runtime/spec.md#requirement-writable-output-handling) writable output handling | partial output |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-032, DG02-U-033, DG02-U-034, DG02-U-035, DG02-U-036, DG02-U-037, DG02-U-038. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [define-consumer-evidence-boundary](../../changes/define-consumer-evidence-boundary/sprint-plan.md).

[Published specification](../../specs/container-runtime/spec.md) and [sprint dispatch](../../SPRINTS.md).
