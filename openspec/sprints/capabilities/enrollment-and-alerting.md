# enrollment-and-alerting sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **monitor service owner and lab operator**. Bring an isolated registry, synthetic runner identities and a known clock to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept service behavior and environment-specific readback. |
| S2. Luna writer | Exercise a disposable enrollment and deduplicated failure alerts. Record what the spoke emits, what the hub stores and which machine duties remain operator-owned. Start at [tests/test_hub_enroll_heartbeat.py](../../../tests/test_hub_enroll_heartbeat.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for service behavior and environment-specific readback. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`mon-enroll-01`](../../specs/enrollment-and-alerting/spec.md#requirement-talk-home-enrollment-over-the-local-network) Talk-home enrollment over the local network | first enrollment / revoked runner |
| [`mon-alert-01`](../../specs/enrollment-and-alerting/spec.md#requirement-deduplicated-failure-alerts-outbound-only) Deduplicated failure alerts, outbound-only | repeated stall |
| [`mon-monitor-hub-01`](../../specs/enrollment-and-alerting/spec.md#requirement-monitor-hub-machine-duties-stay-off-repo) monitor-hub machine duties stay off-repo | fresh monitor-hub rebuild |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-044, DG02-U-045, DG02-U-046. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [qualify-monitor-recovery](../../changes/qualify-monitor-recovery/sprint-plan.md).

[Published specification](../../specs/enrollment-and-alerting/spec.md) and [sprint dispatch](../../SPRINTS.md).
