# Spec Delta

## MODIFIED Requirements

### Requirement: Templates run the gates they name
<!-- id: ci-run-01 -->
Every gate a template job lists SHALL actually execute in that job's environment — with the history, dependencies, and permissions it needs — or report an explicit SKIPPED state; no template SHALL ship a configuration under which a named gate cannot pass.

#### Scenario: scheduled drift run
- **WHEN** the drift-scan template runs on a fresh consumer
- **THEN** the regression arm diffs the real tag window (full history fetched) and the semantic arm runs with its parser installed, and every gate reports PASS, FAIL, or SKIPPED in the summary

#### Scenario: TypeScript consumer
- **WHEN** the consumer has TS/JS files
- **THEN** the template installs typescript@5 before the semantic arm

#### Scenario: clean consumer provisions pinned tooling
- **WHEN** a consumer runs the copied drift-scan workflow without `.gitmodules`
- **THEN** the workflow checks out DevGate at its declared full SHA under `.devgate/`, verifies required scripts and root placement, and runs named gates only after preflight passes

#### Scenario: incomplete tooling checkout
- **WHEN** the SHA is malformed or required checkout files are missing
- **THEN** the workflow fails before any gate is reported as passing
