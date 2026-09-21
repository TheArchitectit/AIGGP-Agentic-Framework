## ADDED Requirements

### Requirement: release provenance continuity

The first unified release SHALL include a machine-readable manifest naming the Agent Guardrails and DevGate cutover commits, imported tag map, policy-bundle digest, schema version, build workflow identity, and conformance evidence.

#### Scenario: artifact cannot name both parents

Given a candidate AIGGP release missing either predecessor commit, when release validation runs, then publishing SHALL fail.

### Requirement: compatibility window

Each supported consumer route SHALL have either a tested redirect/shim or an owner-approved breaking migration. Compatibility duration and removal criteria SHALL be written before cutover.

#### Scenario: pinned reusable workflow

Given a consumer pinned to a DevGate reusable workflow at the old repository, when the repository becomes read-only, then the documented shim or replacement reference SHALL still execute during the compatibility window.

### Requirement: single canonical writer

After CANONICAL, code changes SHALL land only in the unified repository. The archived repositories SHALL reject ordinary writes and SHALL direct contributors to AIGGP.

#### Scenario: post-cutover commit to DevGate

Given a new commit on standalone DevGate after canonical cutover, when divergence monitoring runs, then it SHALL raise a P0 migration incident until the commit is represented or explicitly rejected in the unified ledger.

### Requirement: release namespace safety

Unified versions SHALL use an AIGGP release namespace and SHALL NOT impersonate a predecessor release number. Package names and container tags SHALL have documented continuity or deprecation mappings.

#### Scenario: ambiguous v3.7.1

Given Guardrails v3.7.1 already exists, when an AIGGP release attempts to reuse v3.7.1 without namespace qualification, then release validation SHALL block.
