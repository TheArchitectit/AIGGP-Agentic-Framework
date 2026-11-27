# baseline-ownership sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **framework gate maintainer**. Bring a disposable project, the gate revision and an explicit scan scope to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept measured scope, diagnostic and exit disposition. |
| S2. Luna writer | Prepare an upstream layout and a consumer overlay. Verify each failure registry entry lands in the owning repository and that the bundled baseline identifies only its project. Start at [tests/test_baseline_ownership_check.py](../../../tests/test_baseline_ownership_check.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for measured scope, diagnostic and exit disposition. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`base-own-01`](../../specs/baseline-ownership/spec.md#requirement-baseline-contains-only-this-repos-data) Baseline contains only this repo's data | foreign allowlist entry / clean checkout is warning-free |
| [`base-write-01`](../../specs/baseline-ownership/spec.md#requirement-project-bugs-land-in-the-project-overlay) Project bugs land in the project overlay | default append in consumer / explicit upstream append |
| [`base-specs-01`](../../specs/baseline-ownership/spec.md#requirement-game-dev-gates-and-specs-live-in-this-framework) Game-dev gates and specs live in this framework | traceable bundled specs / no external game-framework pointer |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-015, DG02-U-016, DG02-U-017. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

[Published specification](../../specs/baseline-ownership/spec.md) and [sprint dispatch](../../SPRINTS.md).
