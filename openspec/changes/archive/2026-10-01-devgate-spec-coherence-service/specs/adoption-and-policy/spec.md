## ADDED Requirements

### Requirement: centrally enforced minimums

<!-- id: coh-pol-01 -->

Repository configuration MUST NOT weaken central policy.

#### Scenario: lower severity locally

- **GIVEN** fleet policy marks an assertion high severity
- **WHEN** a repository marks it low
- **THEN** high severity remains effective.

#### Scenario: trusted-but-obsolete central policy

- **GIVEN** a repository pins an older, genuinely signed central policy bundle with weaker requirements
- **WHEN** policy resolution checks anti-rollback rules
- **THEN** the older bundle is rejected unless the control plane has explicitly grandfathered it for a recorded window, and the attempt is visible in fleet reporting.

### Requirement: authenticated policy authority

<!-- id: coh-pol-02 -->

Central policy bundles, the approved evaluator set, the approved signer set, baselines, and exception grants MUST resolve from control-plane trust roots outside repository-controlled input. Repository-supplied digests establish identity but never authority. A repository pull request MUST NOT be able to alter required controls, approve exceptions, or select enforcement stage.

#### Scenario: forged approval

- **GIVEN** a package whose `approval` block claims an authority without a detached control-plane approval record binding that digest
- **WHEN** policy resolution validates approval
- **THEN** the package is treated as unapproved and enforced evaluation cannot PASS on approval-dependent assertions.

#### Scenario: policy substitution attempt

- **GIVEN** a request supplying its own policy root and expected digest with no control-plane binding
- **WHEN** policy resolution runs
- **THEN** resolution fails (exit 31) rather than evaluating against repository-chosen policy.

### Requirement: bounded advisory stage

<!-- id: coh-pol-03 -->

Every advisory adoption MUST have an owner, start date, expiry, violation baseline, and target next stage.

#### Scenario: advisory expiry

- **GIVEN** the maximum advisory age is reached
- **WHEN** no approved renewal exists
- **THEN** new and existing required violations block according to central escalation policy.

### Requirement: no-regression ratchet

<!-- id: coh-pol-04 -->

At Stage 2, the baseline MUST be a ceiling rather than an allowance. Baseline entries are finding fingerprints, not counts.

#### Scenario: four existing and one new violation

- **GIVEN** four fingerprinted baseline violations
- **WHEN** a fifth violation appears
- **THEN** the new violation blocks even if the total remains below a broad numeric budget.

#### Scenario: one fixed, one new, count unchanged

- **GIVEN** a baseline of 13 fingerprints where one is remediated and a different new violation appears
- **WHEN** Stage 2 evaluation runs
- **THEN** the new fingerprint blocks despite the total remaining 13; numeric-count equality is not a pass condition.

### Requirement: finding fingerprint definition

<!-- id: coh-pol-05 -->

A baseline fingerprint MUST be defined over stable content: assertion ID and version, normalized subject location, and a content-derived violation key — never over digests of the whole subject or of timestamps. The fingerprint schema MUST define behavior when an assertion version increments or severity changes for an existing debt item.

#### Scenario: severity escalation of baseline debt

- **GIVEN** a baseline violation whose assertion severity is raised by central policy
- **WHEN** the next Stage 2 evaluation runs
- **THEN** the escalated item blocks per central policy or requires a newly approved, expiring exception; it does not silently inherit advisory treatment.

#### Scenario: recurrence after remediation

- **GIVEN** a baseline entry removed after accepted remediation
- **WHEN** the same fingerprint reappears later
- **THEN** it is treated as a new violation and blocks under the ratchet.

### Requirement: scoped exceptions

<!-- id: coh-pol-06 -->

Exceptions MUST be narrow, expiring, attributable, and reviewable.

#### Scenario: wildcard exception

- **GIVEN** an exception applies to all assertions
- **WHEN** policy validation runs
- **THEN** the exception is rejected.

#### Scenario: exception never rewrites outcome

- **GIVEN** a valid, unexpired exception covering a violated assertion
- **WHEN** the decision is computed
- **THEN** the ledger entry remains VIOLATED with enforcement `EXCEPTION-ADVISORY` and the exception identity is recorded; the outcome is never rewritten to SATISFIED.

### Requirement: enforcement boundary is external

<!-- id: coh-pol-07 -->

Enforcement MUST be anchored in configuration the repository cannot unilaterally change: required status checks, rulesets, or a promotion controller bound to the trusted result producer and the exact candidate digest. Presence of a workflow file in the repository is not enforcement; removal of the workflow MUST NOT remove the gate.

#### Scenario: workflow deleted

- **GIVEN** an enforced repository whose coherence workflow file is deleted in a pull request
- **WHEN** the external required-check boundary evaluates
- **THEN** the missing required check blocks the merge or promotion independently of repository content.

#### Scenario: result from another candidate

- **GIVEN** a valid PASS attestation for subject digest D1 presented for promotion of digest D2
- **WHEN** the promotion consumer verifies binding
- **THEN** promotion is refused; attestations bind exact subject digests.
