## Requirement: isolated baselines

The shared baseline SHALL contain no consuming-repo allowlists. Per-repo exceptions SHALL live in the consuming repo's overlay with scope, reason, and expiry.

### Scenario: contaminated baseline

Given a baseline containing rad-gateway or gamerepo01 allowlists, when baseline validation runs, then it SHALL FAIL and name each foreign entry.

## Requirement: faithful severity mapping

Dependency audit SHALL map upstream HIGH and CRITICAL advisories to blocking severity by default. Downgrading SHALL require a scoped, expiring waiver.

### Scenario: high-severity runtime vulnerability

Given a HIGH runtime vulnerability in a dependency, when the audit gate runs without a waiver, then it SHALL FAIL the gate.

## Requirement: path confinement

Gates SHALL refuse to read outside the audited tree. Path traversal in scanned content SHALL be reported as a finding, not followed.

### Scenario: traversal payload

Given a scanned file referencing ../../ paths, when the gate processes it, then it SHALL NOT read outside the tree and SHALL record the attempt.
