# subjects-3d sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **art workflow and consuming-product owners**. Bring a synthetic asset manifest, target declaration and rights or capture records where applicable to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept asset-specific evidence and outstanding external acceptance. |
| S2. Luna writer | Bind synthetic parts and capture configuration to a subject manifest. Compare the result before and after a repair and require fresh evidence for the changed subject. Start at [tests/test_hub_coherence_3d_slice.py](../../../tests/test_hub_coherence_3d_slice.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for asset-specific evidence and outstanding external acceptance. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`coh-3d-01`](../../specs/subjects-3d/spec.md#requirement-3d-subject-manifest) 3D subject manifest | any part changes |
| [`coh-3d-02`](../../specs/subjects-3d/spec.md#requirement-repair-invalidates-prior-results) repair invalidates prior results | repaired bundle presented with old attestation |
| [`coh-3d-03`](../../specs/subjects-3d/spec.md#requirement-pipeline-consumes-the-common-contract) pipeline consumes the common contract | 3D asset candidate passes / no pipeline-specific branching |
| [`coh-3d-04`](../../specs/subjects-3d/spec.md#requirement-captures-are-declared-inputs) captures are declared inputs | capture regenerated differently |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-112, DG02-U-113, DG02-U-114, DG02-U-115. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [qualify-dg02-spec-3d-fleet-gaps](../../changes/qualify-dg02-spec-3d-fleet-gaps/sprint-plan.md).

[Published specification](../../specs/subjects-3d/spec.md) and [sprint dispatch](../../SPRINTS.md).
