# framework-ci sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **framework and consumer ci owners**. Bring a scoped fixture repository, an approved tool pin and the designated job lane to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept candidate-specific check and checkout provenance. |
| S2. Luna writer | Map each required job to its exact candidate, checkout and runner. Record failed, missing and skipped steps individually and verify the repository's own gate invocations. Start at [tests/test_fw_guards.py](../../../tests/test_fw_guards.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for candidate-specific check and checkout provenance. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`fw-ci-01`](../../specs/framework-ci/spec.md#requirement-the-framework-runs-its-own-tests-in-ci) The framework runs its own tests in CI | a test file stops being collected / pull request gating |
| [`fw-ci-02`](../../specs/framework-ci/spec.md#requirement-the-framework-applies-its-own-gates-to-itself) The framework applies its own gates to itself | self-scan warning / vacuous gate run |
| [`fw-ci-03`](../../specs/framework-ci/spec.md#requirement-workflow-actions-are-digest-or-sha-pinned) Workflow actions are digest or SHA pinned | unpinned action introduced |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-059, DG02-U-060, DG02-U-061. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [gate-scope-honesty](../../changes/gate-scope-honesty/sprint-plan.md).

[Published specification](../../specs/framework-ci/spec.md) and [sprint dispatch](../../SPRINTS.md).

## Active change routing

The [detached corruption range review](../../changes/archive/2026-11-27-consume-detached-corruption-review/sprint-plan.md) records the archived `framework-ci` test-floor and suite-inventory delta. The detached-range change completed its package tasks; preserve the independent CI gates and do not infer protected rollout from local fixtures.
