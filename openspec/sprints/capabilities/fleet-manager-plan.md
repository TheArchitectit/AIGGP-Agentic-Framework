# fleet-manager-plan sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **fleet manager maintainer and the operator for any live lane**. Bring disposable fleet records or a boundary package with declared inputs to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept package behavior and any separate operator-owned claim. |
| S2. Luna writer | Build a plan against frozen desired state. Compare accepted apply, stale plan and repeated apply receipts while preserving the original revision. Start at [fleet-manager/tests/test_plan_apply_v1.py](../../../fleet-manager/tests/test_plan_apply_v1.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for package behavior and any separate operator-owned claim. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`fleet-002-01`](../../specs/fleet-manager-plan/spec.md#requirement-a-plan-is-deterministic-complete-and-impossible-to-edit) A plan is deterministic, complete, and impossible to edit | the same work against the same revision / a plan is edited after it was built / a change that cannot happen / capacity impact |
| [`fleet-002-02`](../../specs/fleet-manager-plan/spec.md#requirement-an-apply-is-bound-to-its-revision-and-its-principal) An apply is bound to its revision and its principal | the state moved on / a destructive change without authority / a plan that no longer holds |
| [`fleet-002-03`](../../specs/fleet-manager-plan/spec.md#requirement-retry-is-idempotent-by-key-and-a-key-covers-one-plan) Retry is idempotent by key, and a key covers one plan | the client retries after a timeout / a key is widened to cover other work |
| [`fleet-002-04`](../../specs/fleet-manager-plan/spec.md#requirement-the-audit-log-is-append-only-and-cannot-be-back-dated) The audit log is append-only and cannot be back-dated | a gap or a rewrite / a refusal is recorded / a value offered as a reason |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-153, DG02-U-154, DG02-U-155, DG02-U-156. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md). A caller could replace a simulated capacity summary without changing the plan ID. Follow [the active extraction/lifecycle/planning qualification](../../changes/qualify-dg02-extraction-lifecycle-plan-gaps/sprint-plan.md).

[Published specification](../../specs/fleet-manager-plan/spec.md) and [sprint dispatch](../../SPRINTS.md).
