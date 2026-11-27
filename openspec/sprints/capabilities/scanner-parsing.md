# scanner-parsing sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **framework gate maintainer**. Bring a disposable project, the gate revision and an explicit scan scope to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept measured scope, diagnostic and exit disposition. |
| S2. Luna writer | Use the declared engine-specific fixtures to check scene inventory, Rust test scope and file-size classification. Record parser decisions per file. Start at [tests/test_regression_sizes.py](../../../tests/test_regression_sizes.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for measured scope, diagnostic and exit disposition. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`gate-tscn-01`](../../specs/scanner-parsing/spec.md#requirement-godot-scene-parsing) Godot scene parsing | minimal valid scene / nested button path / genuine orphan |
| [`gate-rstest-01`](../../specs/scanner-parsing/spec.md#requirement-rust-test-scope-exemption) Rust test-scope exemption | single-line module opener / production line still gated |
| [`gate-size-01`](../../specs/scanner-parsing/spec.md#requirement-test-file-sizing) Test file sizing | pytest file over source limit |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-102, DG02-U-103, DG02-U-104. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [qualify-dg02-monitor-scanner-security-gaps](../../changes/qualify-dg02-monitor-scanner-security-gaps/sprint-plan.md).

[Published specification](../../specs/scanner-parsing/spec.md) and [sprint dispatch](../../SPRINTS.md).
