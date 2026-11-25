# Spec Delta

## ADDED Requirements

### Requirement: Tracked shebang entry points match their index mode
<!-- id: fw-ci-04 -->
Every tracked file that declares a shebang entry point SHALL be committed with Git index mode `100755`; the executable-integrity check SHALL fail on a mismatch and identify the affected path.

#### Scenario: shebang test entry point is committed non-executable
- **GIVEN** a tracked test file declares a Python shebang and direct test-runner entry point
- **WHEN** the executable-integrity gate reads its Git index mode as `100644`
- **THEN** the gate fails and names the file and index-mode remediation

#### Scenario: drift test entry point has executable index mode
- **GIVEN** the drift template test is tracked with mode `100755`
- **WHEN** it is run directly and the executable-integrity gate scans the index
- **THEN** the test passes and the gate reports all tracked shebang entry points as executable
