# rule-coverage-truth sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **framework gate maintainer**. Bring a disposable project, the gate revision and an explicit scan scope to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept measured scope, diagnostic and exit disposition. |
| S2. Luna writer | Compare enabled rules and per-statement detail with the reported numerator and denominator. Include repeated IDs in distinct spec sources. Start at [tests/test_spec_traceability.py](../../../tests/test_spec_traceability.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for measured scope, diagnostic and exit disposition. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`rule-truth-01`](../../specs/rule-coverage-truth/spec.md#requirement-enabled-means-enforced) Enabled means enforced | semantic rule without checker / documented coverage matches shipped coverage |
| [`rule-behavior-01`](../../specs/rule-coverage-truth/spec.md#requirement-behavior-rules-live-in-skills) Behavior rules live in skills | extracted-rules removal |
| [`rule-marker-01`](../../specs/rule-coverage-truth/spec.md#requirement-language-aware-spec-markers) Language-aware spec markers | Python marker |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-095, DG02-U-096, DG02-U-097. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [gate-scope-honesty](../../changes/gate-scope-honesty/sprint-plan.md), [qualify-dg02-monitor-scanner-security-gaps](../../changes/qualify-dg02-monitor-scanner-security-gaps/sprint-plan.md), [qualify-dg02-package-release-rule-gaps](../../changes/qualify-dg02-package-release-rule-gaps/sprint-plan.md).

[Published specification](../../specs/rule-coverage-truth/spec.md) and [sprint dispatch](../../SPRINTS.md).
