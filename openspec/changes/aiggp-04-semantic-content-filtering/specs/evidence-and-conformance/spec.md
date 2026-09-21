## ADDED Requirements

### Requirement: auditable redaction

Redacted content SHALL be recorded as a content hash plus category metadata in the evidence envelope. Raw sensitive payloads SHALL NOT be written to the ledger.

#### Scenario: secret redaction

Given a commit containing a credential, when filtering redacts it, then the envelope SHALL carry the hash and category, and the ledger SHALL contain no plaintext secret.

### Requirement: per-category conformance corpora

Each category SHALL have a versioned detection corpus and benign corpus. Verified status SHALL require meeting declared detection and false-positive budgets on the pinned corpus versions.

#### Scenario: false-positive budget breach

Given a category exceeding its benign-corpus budget, when the release gate runs, then it SHALL FAIL with measured rates.

### Requirement: version-bump invalidation

A classifier version change SHALL invalidate prior conformance claims until the corpus is re-run at the new version.

#### Scenario: silent upgrade flagged

Given a deployment whose classifier updated without a corpus re-run, when conformance status is queried, then the category SHALL report stale.
