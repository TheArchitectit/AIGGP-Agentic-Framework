# fleet-app-enrollment sprint plan

At `cb2205c` the index recorded **UNKNOWN**. Start by locating the implementation and a measurable entry point. Record missing or externally held evidence before selecting an implementation change.

Route acceptance to the **fleet manager maintainer and the operator for any live lane**. Bring disposable fleet records or a boundary package with declared inputs to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept package behavior and any separate operator-owned claim. |
| S2. Luna writer | Inventory all installation pages in fixtures and compare dry-run, replay and archived-repository results. The operator owns any later live enrollment receipt. Start at [tests/test_fleet_app_enroll.py](../../../tests/test_fleet_app_enroll.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for package behavior and any separate operator-owned claim. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`fleet-app-01`](../../specs/fleet-app-enrollment/spec.md#requirement-discovery-follows-every-installation-page) Discovery follows every installation page | the installation spans multiple pages / a next link leaves the GitHub API |
| [`fleet-app-02`](../../specs/fleet-app-enrollment/spec.md#requirement-archived-repositories-are-skipped-visibly) Archived repositories are skipped visibly | one archived repository in the listing |
| [`fleet-app-03`](../../specs/fleet-app-enrollment/spec.md#requirement-variable-reconciliation-is-idempotent) Variable reconciliation is idempotent | absent, wrong, and matching values |
| [`fleet-app-04`](../../specs/fleet-app-enrollment/spec.md#requirement-secret-creation-is-idempotent-and-non-destructive) Secret creation is idempotent and non-destructive | the secret already exists / explicit rotation |
| [`fleet-app-05`](../../specs/fleet-app-enrollment/spec.md#requirement-dry-run-performs-zero-writes) Dry run performs zero writes | unconfigured repository in dry-run |
| [`fleet-app-06`](../../specs/fleet-app-enrollment/spec.md#requirement-app-authentication-fails-closed) App authentication fails closed | only half the pair is configured / missing installation token |
| [`fleet-app-07`](../../specs/fleet-app-enrollment/spec.md#requirement-execution-is-scheduled-and-fleet-only) Execution is scheduled and fleet-only | trigger surface / a scheduled run applies / a manual dispatch plans by default |
| [`fleet-app-08`](../../specs/fleet-app-enrollment/spec.md#requirement-no-credential-reaches-a-report-or-a-log) No credential reaches a report or a log | an applied run creates a secret |
| [`fleet-app-09`](../../specs/fleet-app-enrollment/spec.md#requirement-per-repository-errors-do-not-stop-the-fleet) Per-repository errors do not stop the fleet | one repository fails, another is healthy |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

Coordinate overlapping work with [dg-05-fleet-app-enrollment-traceability](../../changes/dg-05-fleet-app-enrollment-traceability/sprint-plan.md).

[Published specification](../../specs/fleet-app-enrollment/spec.md) and [sprint dispatch](../../SPRINTS.md).
