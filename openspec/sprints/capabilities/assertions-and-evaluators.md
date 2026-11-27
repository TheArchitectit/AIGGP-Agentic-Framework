# assertions-and-evaluators sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **coherence service maintainer**. Bring pinned context, subject, policy and evaluator artifacts to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept the subject identity, decision and sealed evidence. |
| S2. Luna writer | Evaluate a small assertion set against approved identity values. Distinguish advice from canonical findings and compare finding keys across equivalent input. Start at [tests/test_hub_coherence_assertion_schema.py](../../../tests/test_hub_coherence_assertion_schema.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for the subject identity, decision and sealed evidence. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`coh-assert-01`](../../specs/assertions-and-evaluators/spec.md#requirement-assertion-schema-is-operational) assertion schema is operational | assertion missing owner or requirement ref / parameter schema violation |
| [`coh-assert-02`](../../specs/assertions-and-evaluators/spec.md#requirement-identity-assertions-compare-against-approved-values) identity assertions compare against approved values | consistent but unapproved identity / selector resolves to nothing |
| [`coh-assert-03`](../../specs/assertions-and-evaluators/spec.md#requirement-release-claim-binding-order) release-claim binding order | self-referential release manifest / manifest for a different build |
| [`coh-assert-04`](../../specs/assertions-and-evaluators/spec.md#requirement-traceability-checks-are-separated-by-phase) traceability checks are separated by phase | planning check runs first |
| [`coh-assert-05`](../../specs/assertions-and-evaluators/spec.md#requirement-model-generated-advice-is-non-canonical) model-generated advice is non-canonical | advisory vision observation / reproducible rubric met |
| [`coh-assert-06`](../../specs/assertions-and-evaluators/spec.md#requirement-finding-key-stability) finding key stability | same violation across runs |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-009, DG02-U-010, DG02-U-011, DG02-U-012, DG02-U-013, DG02-U-014. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [define-consumer-evidence-boundary](../../changes/define-consumer-evidence-boundary/sprint-plan.md).

[Published specification](../../specs/assertions-and-evaluators/spec.md) and [sprint dispatch](../../SPRINTS.md).
