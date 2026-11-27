# hub-architecture sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **monitor service owner and lab operator**. Bring an isolated registry, synthetic runner identities and a known clock to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept service behavior and environment-specific readback. |
| S2. Luna writer | Qualify the single writer, spoke watchdog and local-only network posture using isolated test state. Reconcile hub and spoke observations after restart. Start at [tests/test_hub_watchdog.py](../../../tests/test_hub_watchdog.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for service behavior and environment-specific readback. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`mon-hub-01`](../../specs/hub-architecture/spec.md#requirement-single-hub-on-monitor-hub) Single hub on monitor-hub | hub is the only well-known endpoint |
| [`mon-channels-01`](../../specs/hub-architecture/spec.md#requirement-dual-evidence-channels) Dual evidence channels | unenrolled runner still watched |
| [`mon-registry-01`](../../specs/hub-architecture/spec.md#requirement-registry-is-instance-state-never-committed) Registry is instance state, never committed | public-repo hygiene |
| [`mon-deadman-01`](../../specs/hub-architecture/spec.md#requirement-hub-death-is-detected-by-a-spoke) Hub death is detected by a spoke | hub container dies / hub alive but polling disabled |
| [`mon-local-01`](../../specs/hub-architecture/spec.md#requirement-local-only-network-posture) Local-only network posture | no inbound firewall rules |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-073, DG02-U-074, DG02-U-075, DG02-U-076, DG02-U-077. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [qualify-dg02-hub-integration-gaps](../../changes/qualify-dg02-hub-integration-gaps/sprint-plan.md), [qualify-monitor-recovery](../../changes/qualify-monitor-recovery/sprint-plan.md).

[Published specification](../../specs/hub-architecture/spec.md) and [sprint dispatch](../../SPRINTS.md).
