# gitlab-restore-deferral-review sprint plan

At `cb2205c` the index recorded **UNKNOWN**. Start by locating the implementation and a measurable entry point. Record missing or externally held evidence before selecting an implementation change.

Route acceptance to the **gitlab option owner and selecting operator**. Bring the recorded GitLab adoption decision and the hermetic fixture to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept conditional live results only on owner activation. |
| S2. Luna writer | Retain the existing conditional restore decision. A selecting operator must supply a disposable restore target and dated recovery receipt before claiming live recovery. Start at [docs/GITLAB-FORGE.md](../../../docs/GITLAB-FORGE.md). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | Independently verify the dated owner decision. Replay live acceptance only when the owner has activated it. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for conditional live results only on owner activation. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`glf-oi-003`](../../specs/gitlab-restore-deferral-review/spec.md#requirement-restore-review-follows-the-selected-instance-decision) Restore review follows the selected-instance decision | owner reviews the restore deferral |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

Coordinate overlapping work with [add-gitlab-forge-support](../../changes/add-gitlab-forge-support/sprint-plan.md).

[Published specification](../../specs/gitlab-restore-deferral-review/spec.md) and [sprint dispatch](../../SPRINTS.md).
