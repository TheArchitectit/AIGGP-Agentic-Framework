# Data corruption range review

## Purpose

Keep corruption checks effective while permitting an external authority to acknowledge one exact, reviewed committed range.

## ADDED Requirements

### Requirement: Range findings require detached exact review
<!-- id: fw-corruption-02 -->
When exact-review mode is enabled, the corruption scanner SHALL evaluate the complete committed range without using suppression data from the scanned repository. The canonical repository identity SHALL match the run's reserved `GITHUB_REPOSITORY` when present, or otherwise the verified `origin` identity. Under GitHub Actions the resolved `HEAD` SHALL match the reserved `GITHUB_SHA`. A review MAY acknowledge substitution-flip and mass-rewrite findings only when a detached review document, whose expected digest is supplied outside the scanned repository, matches the canonical repository identity, full base commit, exact target Git tree, and complete inventory of all range failures and warnings. The review SHALL NOT suppress content findings, staged findings, or control-test failures. Missing or stale review data SHALL leave ordinary range findings visible and blocking; malformed explicitly configured review data SHALL fail closed.

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

#### Scenario: unrelated clean range with stale review
- **WHEN** an otherwise valid detached review names another base or target tree and the current range is clean
- **THEN** the clean range passes with a diagnostic that the review did not match
