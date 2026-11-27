# canonical-identity sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **coherence service maintainer**. Bring pinned context, subject, policy and evaluator artifacts to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept the subject identity, decision and sealed evidence. |
| S2. Luna writer | Pin subject, package, image and platform inputs separately. Compare canonical-equivalent input with a changed subject and record each digest domain. Start at [tests/test_coherence_image_identity.py](../../../tests/test_coherence_image_identity.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for the subject identity, decision and sealed evidence. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`coh-id-01`](../../specs/canonical-identity/spec.md#requirement-digest-and-canonicalization-profile) digest and canonicalization profile | golden vectors / line-ending change is a content change |
| [`coh-id-02`](../../specs/canonical-identity/spec.md#requirement-subject-manifest) subject manifest | path escape / input mutated during evaluation |
| [`coh-id-03`](../../specs/canonical-identity/spec.md#requirement-package-normative-digest) package normative digest | normative edit changes identity |
| [`coh-id-04`](../../specs/canonical-identity/spec.md#requirement-image-and-platform-identity) image and platform identity | cross-architecture replay / undeclared profile |
| [`coh-id-05`](../../specs/canonical-identity/spec.md#requirement-domain-separated-digests) domain-separated digests | role confusion attempt |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-018, DG02-U-019, DG02-U-020, DG02-U-021, DG02-U-022. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

[Published specification](../../specs/canonical-identity/spec.md) and [sprint dispatch](../../SPRINTS.md).
