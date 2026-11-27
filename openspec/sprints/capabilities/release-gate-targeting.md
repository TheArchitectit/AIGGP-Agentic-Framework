# release-gate-targeting sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **release owner**. Bring a named candidate and disposable packaging or release fixtures to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept version, target, artifacts and owner disposition. |
| S2. Luna writer | Trace release gates from a synthetic consumer to its actual project tree. Compare package audit classifications against the consumer's dependency scope. Start at [tests/test_regression_audit.py](../../../tests/test_regression_audit.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for version, target, artifacts and owner disposition. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`rel-target-01`](../../specs/release-gate-targeting/spec.md#requirement-gates-evaluate-the-project-being-deployed) Gates evaluate the project being deployed | consumer violation blocks deploy / submodule state is irrelevant |
| [`rel-audit-01`](../../specs/release-gate-targeting/spec.md#requirement-runtime-vulnerability-classification) Runtime vulnerability classification | direct runtime HIGH / dev-only path |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-093, DG02-U-094. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [qualify-dg02-package-release-rule-gaps](../../changes/qualify-dg02-package-release-rule-gaps/sprint-plan.md).

[Published specification](../../specs/release-gate-targeting/spec.md) and [sprint dispatch](../../SPRINTS.md).
