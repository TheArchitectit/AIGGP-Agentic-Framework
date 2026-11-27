# game-regression sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **framework tooling maintainer and the consuming game owner**. Bring a disposable project with explicit engine, session or scene inputs to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept framework behavior and any outstanding consumer evidence. |
| S2. Luna writer | Exercise the project failure registry on an added regression and a clean edit. Capture deterministic gameplay evidence in the consuming repository when a claim requires it. Start at [tests/test_game_regression.py](../../../tests/test_game_regression.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for framework behavior and any outstanding consumer evidence. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`game-reg-04`](../../specs/game-regression/spec.md#requirement-failure-registry-is-append-only) failure registry is append-only | duplicate append is honest |
| [`game-reg-05`](../../specs/game-regression/spec.md#requirement-registered-patterns-block-staged-changes) registered patterns block staged changes | reintroduced null-deref pattern |
| [`game-reg-06`](../../specs/game-regression/spec.md#requirement-determinism-evidence-for-gameplay-crashes) determinism evidence for gameplay crashes | unseeded crash is not comparable |
| [`game-reg-01`](../../specs/game-regression/spec.md#requirement-game-class-pattern-scan) Game-class pattern scan | orphaned signal detected / the check on the next line is not the bug / an unchecked open is still reported / compile-time preload is not a scene-load failure / a comment describing a pattern is not a hit / pre-commit blocking |
| [`game-reg-02`](../../specs/game-regression/spec.md#requirement-registry-patterns-honor-scoping-and-annotations) Registry patterns honor scoping and annotations | glob-scoped registry pattern / annotated line suppressed |
| [`game-reg-03`](../../specs/game-regression/spec.md#requirement-empty-scope-is-not-a-pass) Empty scope is not a pass | empty project |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-062, DG02-U-063, DG02-U-064, DG02-U-065, DG02-U-066, DG02-U-067. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [qualify-dg02-monitor-scanner-security-gaps](../../changes/qualify-dg02-monitor-scanner-security-gaps/sprint-plan.md).

[Published specification](../../specs/game-regression/spec.md) and [sprint dispatch](../../SPRINTS.md).
