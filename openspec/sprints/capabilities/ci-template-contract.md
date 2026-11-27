# ci-template-contract sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **framework and consumer ci owners**. Bring a scoped fixture repository, an approved tool pin and the designated job lane to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept candidate-specific check and checkout provenance. |
| S2. Luna writer | Compare the template's advertised gates with an actual synthetic consumer run. Bind each executed gate to the checked-out tool revision and its expected exit. Start at [tests/test_github_workflow_bootstrap.py](../../../tests/test_github_workflow_bootstrap.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for candidate-specific check and checkout provenance. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`ci-run-01`](../../specs/ci-template-contract/spec.md#requirement-templates-run-the-gates-they-name) Templates run the gates they name | scheduled drift run / TypeScript consumer / clean consumer provisions pinned tooling / incomplete tooling checkout / specs workflow uses the copied tooling pin / text-integrity workflow retains its scan scope |
| [`ci-match-01`](../../specs/ci-template-contract/spec.md#requirement-blocking-checks-match-what-they-describe) Blocking checks match what they describe | environment.yml is not .env / real .env blocked |
| [`ci-self-01`](../../specs/ci-template-contract/spec.md#requirement-the-framework-gates-itself) The framework gates itself | PR checks |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-023, DG02-U-024, DG02-U-025. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [harden-template-runner-portability](../../changes/harden-template-runner-portability/sprint-plan.md), [qualify-consumer-delivery-evidence](../../changes/qualify-consumer-delivery-evidence/sprint-plan.md).

[Published specification](../../specs/ci-template-contract/spec.md) and [sprint dispatch](../../SPRINTS.md).
