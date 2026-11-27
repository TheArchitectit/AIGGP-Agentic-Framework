# runner-monitoring sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **monitor service owner and lab operator**. Bring an isolated registry, synthetic runner identities and a known clock to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept service behavior and environment-specific readback. |
| S2. Luna writer | Review online state, queue assignment, gate result and drift recency independently. Exercise failed telemetry and explicitly retain unavailable observations. Start at [tests/test_hub_monitor.py](../../../tests/test_hub_monitor.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for service behavior and environment-specific readback. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`mon-online-01`](../../specs/runner-monitoring/spec.md#requirement-runner-online-detection) Runner online detection | dead quadlet |
| [`mon-queue-01`](../../specs/runner-monitoring/spec.md#requirement-queue-drain-detection) Queue-drain detection | stalled queue |
| [`mon-gates-01`](../../specs/runner-monitoring/spec.md#requirement-gate-result-tracking) Gate-result tracking | red gate on main |
| [`mon-drift-01`](../../specs/runner-monitoring/spec.md#requirement-drift-scan-recency) Drift-scan recency | overdue drift scan |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-098, DG02-U-099, DG02-U-100, DG02-U-101. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [dg09-gitlab-runner-live-monitoring](../../changes/dg09-gitlab-runner-live-monitoring/sprint-plan.md), [qualify-dg02-monitor-scanner-security-gaps](../../changes/qualify-dg02-monitor-scanner-security-gaps/sprint-plan.md).

[Published specification](../../specs/runner-monitoring/spec.md) and [sprint dispatch](../../SPRINTS.md).
