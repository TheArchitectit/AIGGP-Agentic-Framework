## ADDED Requirements

### Requirement: required-check continuity

Every protected-branch required check SHALL have a documented successor or an explicit retirement decision. Branch protection SHALL NOT be changed until the successor has passed its positive fixture and failed its negative control on the migration branch.

#### Scenario: renamed check disappears

Given an old required check named devgate and a new job named repo-gate, when branch-protection mapping lacks the successor, then the cutover SHALL fail before CANONICAL.

### Requirement: non-vacuous path filtering

CI path filters SHALL execute the correct module and integration jobs for policy-only, DevGate-only, kernel/schema-only, and cross-module changes. A zero-job or skipped-all result SHALL be EMPTY, never green.

#### Scenario: shared schema changes

Given a change only under schemas/, when CI evaluates path filters, then both policy and DevGate contract suites plus kernel conformance SHALL run.

### Requirement: dual proof

Before canonical cutover, old and new execution paths SHALL run the same golden corpus and adversarial negative controls. Verdicts and evidence SHALL match under the declared equivalence rules; tolerated differences SHALL be documented fields such as path prefixes and timestamps, never findings or severity.

#### Scenario: new path skips a fixture

Given a negative-control fixture that fails in standalone DevGate, when the unified path returns PASS, SKIP, or EMPTY, then migration SHALL stop as P0.

### Requirement: secret and permission minimization

CI secrets SHALL be re-bound by class and least privilege. Secret values SHALL NOT be copied into repository files, migration logs, fixtures, or manifests. Permissions and environment approvals SHALL be tested before old credentials are revoked.

#### Scenario: release token appears in manifest

Given a migration artifact containing a credential value, when secret scanning runs, then acceptance SHALL fail and the credential SHALL be rotated under incident procedure.
