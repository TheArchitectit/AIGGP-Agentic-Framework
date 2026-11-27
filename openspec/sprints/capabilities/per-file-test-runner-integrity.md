# per-file-test-runner-integrity sprint plan

At `cb2205c` the index recorded **UNKNOWN**. Start by locating the implementation and a measurable entry point. Record missing or externally held evidence before selecting an implementation change.

Route acceptance to the **framework gate maintainer**. Bring a disposable project, the gate revision and an explicit scan scope to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept measured scope, diagnostic and exit disposition. |
| S2. Luna writer | Exercise a successful file alongside a launch failure. Trace both results to the original invocation and require its aggregate report to show a nonempty count. Start at [tests/test_run_tests_runner.mjs](../../../tests/test_run_tests_runner.mjs). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for measured scope, diagnostic and exit disposition. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`gate-test-launch-01`](../../specs/per-file-test-runner-integrity/spec.md#requirement-per-file-process-launch-failures-are-visible) Per-file process launch failures are visible | A process cannot be started / An initially failed launch succeeds during adjudication |
| [`gate-test-count-01`](../../specs/per-file-test-runner-integrity/spec.md#requirement-ci-checks-the-original-runner-invocation-for-non-vacuity) CI checks the original runner invocation for non-vacuity | Successful nonempty runner report / Unusable runner evidence |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

[Published specification](../../specs/per-file-test-runner-integrity/spec.md) and [sprint dispatch](../../SPRINTS.md).
