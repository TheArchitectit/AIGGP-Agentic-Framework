# Release gate targeting and audit classification

## Purpose

Release and drift gates target the right tree at the right scope: release gates evaluate the project being published, drift sweeps run on a schedule rather than the PR path, and gate findings carry an audit classification instead of a bare pass/fail.

## Requirements


### Requirement: Gates evaluate the project being deployed
<!-- id: rel-target-01 -->
Every gate invoked by deploy.sh (regression check, pattern scan, size check,
package audit) SHALL evaluate the consuming project's tree and diff, never
the DevGate submodule's, regardless of the pipeline's working directory.

#### Scenario: consumer violation blocks deploy
- **WHEN** the project being deployed contains a blocking regression finding
  and the DevGate submodule is clean
- **THEN** deploy.sh aborts before the version bump and names the project's
  file in the failure

#### Scenario: submodule state is irrelevant
- **WHEN** the DevGate submodule has uncommitted changes but the project is
  clean
- **THEN** the clean-tree check evaluates the project and proceeds

### Requirement: Runtime vulnerability classification
<!-- id: rel-audit-01 -->
The package audit SHALL classify a vulnerability as runtime-blocking when the
vulnerable package is a direct runtime dependency (npm `isDirect` and listed
in `dependencies`) or when any dependent in `effects` is a runtime
dependency; otherwise it SHALL warn.

#### Scenario: direct runtime HIGH
- **WHEN** a direct entry in `dependencies` has a HIGH advisory
- **THEN** the audit counts it blocking and `--pre-commit` exits 1

#### Scenario: dev-only path
- **WHEN** the vulnerable package is reachable only through devDependencies
- **THEN** the audit reports a warning and does not block
