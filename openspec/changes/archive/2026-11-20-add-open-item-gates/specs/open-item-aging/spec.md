# Open-Item Aging

## ADDED Requirements

### Requirement: An aged open item must carry a triage disposition
<!-- id: oia-01 -->
An open item older than the configured threshold MUST carry a disposition of `fixed`,
`deferred`, or `not-actionable` in the append-only triage ledger, keyed by the item's
stable identifier. An aged item with no disposition MUST fail, named individually rather
than aggregated.

#### Scenario: 70-day-old untriaged item
- **WHEN** an open item's source date is 70 days old and the ledger has no row for it
- **THEN** the gate fails naming that item and its age

#### Scenario: invalid disposition
- **WHEN** a disposition value falls outside the three permitted values
- **THEN** the gate fails, because a near-miss must not read as triaged

### Requirement: Deferral expires and carries a reason
<!-- id: oia-02 -->
A `deferred` disposition MUST include both a `reason` and a `review_by` date. Past
`review_by` the item MUST fail again. A `deferred` row lacking either field MUST fail.

#### Scenario: expired deferral
- **WHEN** a `review_by` date has passed
- **THEN** the gate fails stating re-triage is required

#### Scenario: open-ended deferral
- **WHEN** a `deferred` row has no `review_by`
- **THEN** the gate fails, because deferral without expiry is indistinguishable from being forgotten

### Requirement: An unparseable age fails rather than defaulting
<!-- id: oia-03 -->
An open row whose source date cannot be parsed MUST fail. It MUST NOT default to the
current date, because an item that cannot be aged can never age out and becomes permanent
by accident rather than by decision.

#### Scenario: row with no date
- **WHEN** an open row carries no parseable source date
- **THEN** the gate fails naming the line

### Requirement: A vacuous scan is never a pass
<!-- id: oia-04 -->
When no open rows parse, the gate MUST exit with the nothing-scanned code and MUST NOT
report success.

#### Scenario: empty backlog
- **WHEN** the backlog contains no parseable open rows
- **THEN** the gate refuses with a vacuous-pass message
