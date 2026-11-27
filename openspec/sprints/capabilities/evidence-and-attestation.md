# evidence-and-attestation sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **coherence service maintainer**. Bring pinned context, subject, policy and evaluator artifacts to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept the subject identity, decision and sealed evidence. |
| S2. Luna writer | Bind result, manifest, subject and detached approval by digest. Check authorized retention against a synthetic fixture and compare accepted and rejected approval records. Start at [tests/test_hub_coherence_attestation.py](../../../tests/test_hub_coherence_attestation.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for the subject identity, decision and sealed evidence. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`coh-ev-01`](../../specs/evidence-and-attestation/spec.md#requirement-acyclic-sealing-order) acyclic sealing order | re-signing leaves decision unchanged / attestation field absent from decision |
| [`coh-ev-02`](../../specs/evidence-and-attestation/spec.md#requirement-complete-evidence-manifest) complete evidence manifest | evidence write failure / retryable remote upload after seal |
| [`coh-ev-03`](../../specs/evidence-and-attestation/spec.md#requirement-reproducible-findings) reproducible findings | reproduce without the original runner |
| [`coh-ev-04`](../../specs/evidence-and-attestation/spec.md#requirement-authorized-input-retention) authorized input retention | evidence outlives retention |
| [`coh-ev-05`](../../specs/evidence-and-attestation/spec.md#requirement-attestation-binding) attestation binding | result substituted / revoked signer |
| [`coh-ev-06`](../../specs/evidence-and-attestation/spec.md#requirement-minimal-disclosure) minimal disclosure | source contains unrelated sensitive content |
| [`coh-ev-07`](../../specs/evidence-and-attestation/spec.md#requirement-approval-records-are-detached) approval records are detached | approval binds exact revision |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-052, DG02-U-053, DG02-U-054, DG02-U-055, DG02-U-056, DG02-U-057, DG02-U-058. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [qualify-consumer-delivery-evidence](../../changes/qualify-consumer-delivery-evidence/sprint-plan.md).

[Published specification](../../specs/evidence-and-attestation/spec.md) and [sprint dispatch](../../SPRINTS.md).
