# data-corruption Specification

## Purpose
Keep corruption checks effective while permitting an external authority to acknowledge one exact, reviewed committed range.

## Requirements

### Requirement: Range findings require detached exact review
<!-- id: fw-corruption-02 -->
Exact mode SHALL scan committed ranges without consumer-controlled suppressions. A detached, externally hashed review MAY acknowledge substitution and mass-rewrite findings only when repository, run, full base, exact target tree, and complete finding inventory match. Other findings remain blocking; invalid configured reviews fail closed.

#### Scenario: exact review matches the committed range
- **WHEN** the externally supplied review digest, repository, base commit, target tree, and complete flip and rewrite inventory match the evaluated `BASE..HEAD` range
- **THEN** every finding remains printed as reviewed, those exact findings do not fail the range gate, and all unrelated gates continue normally

#### Scenario: consumer checkout attempts self-approval
- **WHEN** the scanned repository adds or changes a local corruption allowlist or review file
- **THEN** exact-review mode ignores it for range findings and reports any unreviewed finding as a failure

#### Scenario: range changes after review
- **WHEN** a path, mode, rename, content, repository, base, or finding inventory differs from the detached review
- **THEN** the review does not acknowledge the range and the scanner reports ordinary findings and verdicts

#### Scenario: invalid authority data
- **WHEN** a review file is explicitly configured but its digest, location, schema, or required identities are invalid
- **THEN** the scanner fails closed before reporting a passing range

#### Scenario: GitHub run and checkout disagree
- **WHEN** the workflow's reserved `GITHUB_SHA` does not identify the scanner's resolved `HEAD`
- **THEN** exact-review mode fails before scanning, even if a review document names that checkout

#### Scenario: repository identity is replayed to another checkout
- **WHEN** the supplied repository differs from reserved `GITHUB_REPOSITORY`, or from verified `origin` outside Actions
- **THEN** exact-review mode fails before applying any detached review

#### Scenario: content and other gates remain blocking
- **WHEN** a content, staged, control-test, or other non-range finding occurs alongside an acknowledged range
- **THEN** the range review does not suppress that finding or make its gate pass

#### Scenario: unrelated clean range with stale review
- **WHEN** an otherwise valid detached review names another base or target tree and the current range is clean
- **THEN** the clean range passes with a diagnostic that the review did not match
