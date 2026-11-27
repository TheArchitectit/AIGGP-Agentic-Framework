# fleet-manager-domain sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **fleet manager maintainer and the operator for any live lane**. Bring disposable fleet records or a boundary package with declared inputs to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept package behavior and any separate operator-owned claim. |
| S2. Luna writer | Apply assignments, drains and rollouts to a synthetic desired state. Preserve the original revision and retain field-specific refusals for invalid pool and host inputs. Start at [fleet-manager/tests/test_model_v1.py](../../../fleet-manager/tests/test_model_v1.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for package behavior and any separate operator-owned claim. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`fleet-001-01`](../../specs/fleet-manager-domain/spec.md#requirement-desired-state-is-held-by-the-manager-and-it-is-immutable) Desired state is held by the manager, and it is immutable | a transition does not mutate its input / an observation is offered as desired state / the two modules stay apart |
| [`fleet-001-02`](../../specs/fleet-manager-domain/spec.md#requirement-a-pool-declares-its-whole-contract-or-is-refused-by-field) A pool declares its whole contract or is refused by field | a required field is absent / an unknown field appears / Phase 1 is ephemeral-only |
| [`fleet-001-03`](../../specs/fleet-manager-domain/spec.md#requirement-secrets-are-referenced-never-carried) Secrets are referenced, never carried | a value-shaped key appears / a reference carries a blob |
| [`fleet-001-04`](../../specs/fleet-manager-domain/spec.md#requirement-a-host-may-run-a-pool-only-where-capabilities-allow-list-and-state-agree) A host may run a pool only where capabilities, allow-list and state agree | architectures do not intersect / the pool is not on the host's allow-list |
| [`fleet-001-05`](../../specs/fleet-manager-domain/spec.md#requirement-capacity-drain-and-rollout-refuse-impossible-states) Capacity, drain and rollout refuse impossible states | over-capacity / drain with work in flight / a rollout to the current image / a rollout succeeds |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-140, DG02-U-141, DG02-U-142, DG02-U-143, DG02-U-144. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [qualify-dg02-boundary-contract-domain-gaps](../../changes/qualify-dg02-boundary-contract-domain-gaps/sprint-plan.md).

[Published specification](../../specs/fleet-manager-domain/spec.md) and [sprint dispatch](../../SPRINTS.md).
