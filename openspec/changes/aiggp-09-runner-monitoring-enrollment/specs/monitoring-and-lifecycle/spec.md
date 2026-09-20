## Requirement: verified heartbeats

Runners SHALL emit signed heartbeats recorded to the ledger. Missing heartbeats SHALL transition the runner to suspect and then drained per declared windows.

### Scenario: silent runner

Given a runner missing heartbeats beyond the suspect window, when the monitor evaluates, then the runner SHALL be marked suspect and drain SHALL begin.

## Requirement: evidence-only truth

Runner status in every surface SHALL derive from verified ledger evidence. No surface SHALL display trust from unverified sources.

### Scenario: UI trust claim

Given a UI presenting a runner as trusted without current verified evidence, when conformance checks the surface, then it SHALL be flagged as a truth violation.

## Requirement: rehearsed lifecycle

Rollout, canary, drain, and rollback SHALL be implemented as first-class operations with ledger evidence in both directions, and SHALL be exercised by drills in CI.

### Scenario: bad bundle rollback

Given a canary detecting a bad bundle rollout, when rollback executes, then prior signed state SHALL be restored and both the rollout and rollback SHALL appear in the ledger.

## Requirement: secret-class confinement

A runner SHALL receive only the secret classes its trust class and current workload require, delivered ephemerally. Ambient credentials SHALL NOT persist on runners.

### Scenario: cross-class secret request

Given a runner requesting a secret class outside its entitlement, when the broker evaluates, then the request SHALL be denied and logged.
