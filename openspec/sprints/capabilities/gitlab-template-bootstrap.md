# gitlab-template-bootstrap sprint plan

At `cb2205c` the index recorded **UNKNOWN**. Start by locating the implementation and a measurable entry point. Record missing or externally held evidence before selecting an implementation change.

Route acceptance to the **framework and consumer ci owners**. Bring a scoped fixture repository, an approved tool pin and the designated job lane to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept candidate-specific check and checkout provenance. |
| S2. Luna writer | Start from a clean mirror fixture and verify the approved tool pin, bootstrap checkout and gate invocation. Record hermetic and optional live outcomes separately. Start at [tests/test_gitlab_template_bootstrap.py](../../../tests/test_gitlab_template_bootstrap.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for candidate-specific check and checkout provenance. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`glf-template-bootstrap-01`](../../specs/gitlab-template-bootstrap/spec.md#requirement-gitlab-mirror-provisions-pinned-devgate) GitLab mirror provisions pinned DevGate | clean consumer with no submodule / invalid or incomplete checkout / required rule file is missing / mirror points at canonical rule files / hermetic template validation |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

Coordinate overlapping work with [harden-template-runner-portability](../../changes/harden-template-runner-portability/sprint-plan.md).

[Published specification](../../specs/gitlab-template-bootstrap/spec.md) and [sprint dispatch](../../SPRINTS.md).
