# per-file-test-runner-integrity Specification

## Purpose
Define per-file process launch outcomes and verify CI test discovery from the original runner invocation.

## Requirements

### Requirement: Per-file process launch failures are visible
<!-- id: gate-test-launch-01 -->
The per-file test runner SHALL report a child-process launch failure against
the affected file, continue evaluating the remaining discovered files, and
apply its existing solo adjudication. A launch failure that persists in the
solo run SHALL cause an overall nonzero exit.

#### Scenario: A process cannot be started
- **WHEN** a selected test engine fails to launch for one discovered file and a sibling file can run
- **THEN** the runner reports the affected file and launch error, evaluates the sibling, and exits nonzero if adjudication also fails to launch the engine

#### Scenario: An initially failed launch succeeds during adjudication
- **WHEN** the initial launch fails and the solo invocation later executes tests and exits cleanly
- **THEN** the runner records the recovery under its existing flake outcome

### Requirement: CI checks the original runner invocation for non-vacuity
<!-- id: gate-test-count-01 -->
The CI workflow SHALL check the file count from its single recorded runner
execution. An unsuccessful runner, missing completion report or zero file
count SHALL fail the test lane.

#### Scenario: Successful nonempty runner report
- **WHEN** the runner exits successfully and reports one or more discovered files
- **THEN** the workflow verifies the report from the same run

#### Scenario: Unusable runner evidence
- **WHEN** the runner fails or its saved report lacks a positive file count
- **THEN** the workflow fails the test lane without launching a second test run
