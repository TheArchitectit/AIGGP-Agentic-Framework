# Spec Delta: framework-ci (add-framework-ci-pipeline)

## ADDED Requirements

### Requirement: The framework runs its own tests in CI
<!-- id: fw-ci-01 -->
The repository SHALL run its full test suite (Python and Node) on every pull
request and every push to the default branch, and the job SHALL fail when any
test fails or when collection silently drops test files. Test discovery SHALL
be deterministic across contributor environments.

#### Scenario: a test file stops being collected
- **WHEN** a layout or import change causes one or more test files to error at
  collection
- **THEN** the CI job fails or visibly reports the reduced count — never a
  green run over a smaller suite

#### Scenario: pull request gating
- **WHEN** a pull request is opened against the default branch
- **THEN** CI executes the suite and the gates before merge is possible

### Requirement: The framework applies its own gates to itself
<!-- id: fw-ci-02 -->
CI SHALL execute the shipped gates (pattern scan, semantic scan, regression
check over the PR's committed range with a zero-input failure contract,
registry hygiene) against the framework's own tree at the pushed HEAD, and the
framework's tree SHALL be warning-clean under its own default rule set.

#### Scenario: self-scan warning
- **WHEN** the framework's own tree triggers one of its shipped rules
- **THEN** CI surfaces it as a failure or a tracked waiver, never silently

#### Scenario: vacuous gate run
- **WHEN** a gate scope evaluates zero files in CI
- **THEN** the job fails per the gate's zero-input contract

### Requirement: Workflow actions are digest or SHA pinned
<!-- id: fw-ci-03 -->
Every external action referenced by the repository's own workflows SHALL be
pinned by immutable reference (commit SHA), including setup actions; mutable
tags SHALL NOT appear in the framework's own CI files.

#### Scenario: unpinned action introduced
- **WHEN** a workflow edit adds an action referenced only by a mutable tag
- **THEN** review or a lint step flags it before merge
