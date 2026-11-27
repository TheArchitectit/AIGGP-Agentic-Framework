# per-screen-tracking sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **framework tooling maintainer and the consuming game owner**. Bring a disposable project with explicit engine, session or scene inputs to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept framework behavior and any outstanding consumer evidence. |
| S2. Luna writer | Compare a small declared scene inventory with reachable screens and an empty project. Retain orphan identities and the honest empty-scope result. Start at [scripts/scene_inventory.py](../../../scripts/scene_inventory.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for framework behavior and any outstanding consumer evidence. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`screen-inv-01`](../../specs/per-screen-tracking/spec.md#requirement-scene-inventory-and-orphan-detection) Scene inventory and orphan detection | fully wired scene passes / orphaned button fails the gate / handler wired from the scene's script |
| [`screen-inv-02`](../../specs/per-screen-tracking/spec.md#requirement-empty-scene-scope-is-not-a-pass) Empty scene scope is not a pass | non-Godot repository |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-171, DG02-U-172. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [qualify-dg02-monitor-scanner-security-gaps](../../changes/qualify-dg02-monitor-scanner-security-gaps/sprint-plan.md).

[Published specification](../../specs/per-screen-tracking/spec.md) and [sprint dispatch](../../SPRINTS.md).
