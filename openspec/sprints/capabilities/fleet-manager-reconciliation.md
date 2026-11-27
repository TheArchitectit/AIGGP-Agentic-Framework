# fleet-manager-reconciliation sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **fleet manager maintainer and the operator for any live lane**. Bring disposable fleet records or a boundary package with declared inputs to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept package behavior and any separate operator-owned claim. |
| S2. Luna writer | Reconcile the same desired and observed fixtures twice. Compare the proposed actions and evidence for each discrepancy before considering an effect. Start at [fleet-manager/tests/test_reconcile_v1.py](../../../fleet-manager/tests/test_reconcile_v1.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for package behavior and any separate operator-owned claim. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`fleet-003-01`](../../specs/fleet-manager-reconciliation/spec.md#requirement-reconciliation-is-a-deterministic-diff-never-a-state) Reconciliation is a deterministic diff, never a state | a reconciliation is not an apply / two runs over the same fixtures / an edited reconciliation / an order that is not a total order |
| [`fleet-003-02`](../../specs/fleet-manager-reconciliation/spec.md#requirement-convergence-is-bounded-and-every-deferral-is-named) Convergence is bounded and every deferral is named | more work than the cap / a halted reconciler / a pool's disruption budget / every candidate accounted for |
| [`fleet-003-03`](../../specs/fleet-manager-reconciliation/spec.md#requirement-the-reconciler-never-disturbs-work-it-cannot-prove-finished) The reconciler never disturbs work it cannot prove finished | a drain with a runner still reported / an unmanaged runner / a silent host / an unknown host / two reports for one host |
| [`fleet-003-04`](../../specs/fleet-manager-reconciliation/spec.md#requirement-deterministic-fixtures-are-the-evidence) Deterministic fixtures are the evidence | a fixture whose expectation drifts / a malformed report |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-157, DG02-U-158, DG02-U-159, DG02-U-160. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

[Published specification](../../specs/fleet-manager-reconciliation/spec.md) and [sprint dispatch](../../SPRINTS.md).
