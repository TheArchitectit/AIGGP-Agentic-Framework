# gate-execution-contract sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **framework gate maintainer**. Bring a disposable project, the gate revision and an explicit scan scope to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept measured scope, diagnostic and exit disposition. |
| S2. Luna writer | Run from a nested working directory against a known diff. Prove a nonempty input reaches the right project and an empty scope produces the specified refusal. Start at [tests/test_regression_scope.py](../../../tests/test_regression_scope.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for measured scope, diagnostic and exit disposition. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`gate-root-01`](../../specs/gate-execution-contract/spec.md#requirement-project-root-resolution) Project-root resolution | standalone checkout / submodule checkout |
| [`gate-vacuous-01`](../../specs/gate-execution-contract/spec.md#requirement-no-vacuous-green) No vacuous green | test runner finds no files / cargo filter matches no tests |
| [`gate-allwindow-01`](../../specs/gate-execution-contract/spec.md#requirement---all-diff-window) --all diff window | committed violation, clean tree / per-PR scoping |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-070, DG02-U-071, DG02-U-072. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [gate-scope-honesty](../../changes/gate-scope-honesty/sprint-plan.md).

[Published specification](../../specs/gate-execution-contract/spec.md) and [sprint dispatch](../../SPRINTS.md).
