## ADDED Requirements

### Requirement: Consumer qualification proves its declared runner path
<!-- id: ci-consumer-qual-01 -->

The reference delivery workflow SHALL name its supported runner path, pin the
tooling revision, enumerate required checks, and produce exact-revision check
receipts from a nonempty evaluation. It SHALL distinguish an optional runner
path that has not completed the same qualification.

#### Scenario: Hosted reference candidate is evaluated
- **WHEN** a clean reference consumer runs the declared hosted workflow
- **THEN** it runs the declared required checks using the pinned tooling and
  records the checked source revision and runner class

#### Scenario: A required gate cannot run in the selected environment
- **WHEN** a required check depends on a component absent from a runner path
- **THEN** the candidate is reported incomplete and the path is not represented
  as qualified

### Requirement: Consumer promotion verifies candidate and artifact evidence
<!-- id: ci-consumer-qual-02 -->

The reference promotion verifier SHALL match a candidate source revision and
immutable artifact digest with all required successful check receipts, the
consumer's approval reference, and a recovery reference.

#### Scenario: Approved artifact is accepted
- **WHEN** the protected reference path evaluates the approved candidate and
  all its evidence matches the artifact selected for promotion
- **THEN** the verifier records acceptance for that digest

#### Scenario: Evidence is stale, skipped, or for another artifact
- **WHEN** a required result is skipped, missing, unsuccessful, from another
  source revision, or bound to another artifact
- **THEN** the verifier denies promotion and identifies the missing or
  mismatched evidence

### Requirement: Required checks are enforced before protected promotion
<!-- id: ci-consumer-qual-03 -->

The consumer qualification procedure SHALL verify that the configured
protected promotion path requires its declared checks and rejects a failing
candidate before deployment. Observational findings SHALL be reported with
their enforcement status.

#### Scenario: A failed required check is found
- **WHEN** the reference path receives a candidate with a failed required check
- **THEN** no artifact is promoted and the qualification record identifies the
  enforcement point

#### Scenario: A check runs only after promotion
- **WHEN** a check is configured only to report after promotion
- **THEN** qualification records it as observational and does not count it
  toward the required pre-promotion checks
