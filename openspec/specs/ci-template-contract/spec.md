# CI template contract

## Purpose

The shipped GitHub Actions workflow templates are drop-in correct: valid YAML, honest triggers and verdicts, pinned action references, and no advertised behavior the template does not implement. A consumer copying a template gets what its header claims.

## Requirements


### Requirement: Templates run the gates they name
<!-- id: ci-run-01 -->
Every gate a template job lists SHALL actually execute in that job's
environment — with the history, dependencies, and permissions it needs — or
report an explicit SKIPPED state; no template SHALL ship a configuration
under which a named gate cannot pass.

#### Scenario: scheduled drift run
- **WHEN** the drift-scan template runs on a fresh consumer
- **THEN** the regression arm diffs the real tag window (full history
  fetched) and the semantic arm runs with its parser installed, and every
  gate reports PASS, FAIL, or SKIPPED in the summary

#### Scenario: TypeScript consumer
- **WHEN** the consumer has TS/JS files
- **THEN** the template installs typescript@5 before the semantic arm

### Requirement: Blocking checks match what they describe
<!-- id: ci-match-01 -->
Forbidden-file checks SHALL match exact file names and extensions, SHALL
allow the documented exception files (.env.example/.template/.sample), and
SHALL not match unrelated paths by substring or regex metacharacters.

#### Scenario: environment.yml is not .env
- **WHEN** a PR adds `config/environment.yml`
- **THEN** the forbidden-file check does not fire

#### Scenario: real .env blocked
- **WHEN** a PR adds a tracked `.env`
- **THEN** the check fails the job

### Requirement: The framework gates itself
<!-- id: ci-self-01 -->
The DevGate repository SHALL run its own gates and test suite on every pull
request and on main, with the workflow required for merge, and SHALL be
warning-clean on its own scanners.

#### Scenario: PR checks
- **WHEN** a pull request opens against main
- **THEN** pytest, the node fixture tests, the pattern scan, the semantic
  scan, the registry hygiene check, and the regression gate all run
