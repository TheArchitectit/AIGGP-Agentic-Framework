# Spec Delta

## MODIFIED Requirements

### Requirement: Templates run the gates they name
<!-- id: ci-run-01 -->
Every gate a template job lists SHALL actually execute in that job's environment -- with the history, dependencies, and permissions it needs -- or report an explicit SKIPPED state; no template SHALL ship a configuration under which a named gate cannot pass.

#### Scenario: scheduled drift run
- **WHEN** the drift-scan template runs on a fresh consumer
- **THEN** the regression arm diffs the real tag window (full history fetched) and the semantic arm runs with its parser installed, and every gate reports PASS, FAIL, or SKIPPED in the summary

#### Scenario: TypeScript consumer
- **WHEN** the consumer has TS/JS files
- **THEN** the template installs typescript@5 before the semantic arm

#### Scenario: clean consumer provisions pinned tooling
- **WHEN** a consumer runs the copied drift-scan, specs, or text-integrity workflow without `.gitmodules`
- **THEN** that workflow provisions DevGate at its declared full SHA under `.devgate/`, verifies its actual required scripts/data and root placement, and runs named gates only after preflight passes

#### Scenario: incomplete tooling checkout
- **WHEN** the SHA is malformed or required checkout files are missing
- **THEN** the workflow fails before any gate is reported as passing

#### Scenario: specs workflow uses the copied tooling pin
- **WHEN** the specs workflow runs its strict malformed-spec control, traceability report/ratchet, and gap scan
- **THEN** the workflow has already verified the pinned `.devgate/` checkout contains each invoked entry point and supporting required files

#### Scenario: text-integrity workflow retains its scan scope
- **WHEN** the text-integrity workflow runs on a clean consumer with no `.gitmodules`
- **THEN** it provisions the pinned tooling before its charset, encoding, corruption, and declared control tests while preserving the full-history range scan
