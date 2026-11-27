# requirement-id-inventory sprint plan

At `cb2205c` the index recorded **UNKNOWN**. Start by locating the implementation and a measurable entry point. Record missing or externally held evidence before selecting an implementation change.

Route acceptance to the **framework gate maintainer**. Bring a disposable project, the gate revision and an explicit scan scope to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept measured scope, diagnostic and exit disposition. |
| S2. Luna writer | Compare each published requirement heading and ID with the pinned OpenSpec CLI. Retain the malformed-spec refusal and YAML-marker coverage result. Start at [tests/test_spec_id_inventory.py](../../../tests/test_spec_id_inventory.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for measured scope, diagnostic and exit disposition. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`spec-fmt-04`](../../specs/requirement-id-inventory/spec.md#requirement-strict-validation-is-proven-able-to-fail) strict validation is proven able to fail | validator accepts malformed input |
| [`spec-fmt-05`](../../specs/requirement-id-inventory/spec.md#requirement-every-canonical-requirement-heading-has-a-stable-identity) Every canonical requirement heading has a stable identity | missing or malformed identity / valid identity is preserved |
| [`spec-fmt-06`](../../specs/requirement-id-inventory/spec.md#requirement-owned-yaml-workflow-preambles-carry-discoverable-requirement-markers) Owned YAML workflow preambles carry discoverable requirement markers | an owned YAML workflow declares a source marker / a YAML example or fixture is excluded / marker-shaped YAML values are excluded |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

Coordinate overlapping work with [qualify-dg02-spec-3d-fleet-gaps](../../changes/qualify-dg02-spec-3d-fleet-gaps/sprint-plan.md).

[Published specification](../../specs/requirement-id-inventory/spec.md) and [sprint dispatch](../../SPRINTS.md).
