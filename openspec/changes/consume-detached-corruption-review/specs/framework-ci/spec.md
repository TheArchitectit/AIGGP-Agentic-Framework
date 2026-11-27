# Framework CI

## MODIFIED Requirements

### Requirement: The framework runs its own tests in CI
<!-- id: fw-ci-01 -->
The repository SHALL run its full test suite (Python and Node) on every pull request and every push to the default branch, and the job SHALL fail when any test fails or when collection silently drops test files. Test discovery SHALL be deterministic across contributor environments. Every collected Python test suite SHALL have a positive floor in `tests/expected-counts.json`, and CI SHALL fail when the declared suite inventory and floor manifest diverge.

#### Scenario: a test file stops being collected
- **WHEN** a layout or import change causes one or more test files to error at collection
- **THEN** the CI job fails or visibly reports the reduced count — never a green run over a smaller suite

#### Scenario: pull request gating
- **WHEN** a pull request is opened against the default branch
- **THEN** CI executes the suite and the gates before merge is possible

#### Scenario: a new collected suite has no floor
- **WHEN** a delivered change adds a test suite that is collected by CI
- **THEN** the final `tests/expected-counts.json` includes a positive floor for that suite, and the test-suite-floor manifest join passes
