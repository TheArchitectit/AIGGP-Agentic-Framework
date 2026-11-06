# Spec: Fleet Manager contracts

## ADDED Requirements

### Requirement: Cross-boundary documents are versioned and declared
<!-- id: repo-003-01 -->
Every document exchanged between open core and `fleet-manager/` SHALL be
described by a JSON Schema under `fleet-manager/contracts/vN/` and SHALL carry
its own `contract_version` property. The schemas SHALL be closed
(`additionalProperties: false`). Cross-boundary calls SHALL NOT depend on
imported implementation types, database models, or undeclared fields.

#### Scenario: a field nobody declared crosses the boundary

- **WHEN** a producer adds a property that its schema does not declare
- **THEN** validation fails and names the property
- **AND** the document does not arrive at the consumer

#### Scenario: a document carries no version

- **WHEN** a document under the boundary omits `contract_version`
- **THEN** validation fails with a version error
- **AND** the document is not read against the current shape

#### Scenario: a shape change is needed

- **WHEN** any existing v1 shape must change (including an "optional" added
  field, because the schemas are closed)
- **THEN** the change lands as a new `contracts/v2/` directory with its own
  fixtures and tests
- **AND** `contracts/v1/` is not edited in place

### Requirement: A consumer refuses versions it does not implement
<!-- id: repo-003-02 -->
A consumer SHALL refuse a document whose `contract_version` is not the major it
implements, naming the found version and the supported one. A missing,
non-integer, or otherwise unusable version SHALL be refused the same way, never
coerced, defaulted, or read against the current schema.

#### Scenario: a future major arrives

- **WHEN** a consumer implementing v1 receives a document with
  `contract_version: 2`
- **THEN** validation fails with a version error naming both numbers
- **AND** the refusal is a version error, not a list of shape errors from the
  v1 schema

#### Scenario: the version is a string

- **WHEN** `contract_version` is `"1"` rather than `1`
- **THEN** it is refused rather than coerced

### Requirement: Contract tests run in both directions
<!-- id: repo-004-01 -->
Contract tests SHALL run Fleet Manager's consumer against a core-producer
fixture, and Fleet Manager's producer against a core-consumer fixture that
declares, as data, the minimum the core side relies on. The suite SHALL run
from the boundary package alone — no network, no core test tree.

#### Scenario: the other side's document is malformed

- **WHEN** a core-producer fixture is mutated (missing required field, wrong
  type, undeclared field, bad timestamp, out-of-enum value)
- **THEN** every mutation is refused with the offending path named
- **AND** the refusal is a typed contract error, not a leaked `KeyError` or
  `TypeError`

#### Scenario: the core side's minimum changes

- **WHEN** the core-consumer fixture gains a required path or reason code
- **THEN** a producer document that does not satisfy it fails the suite

### Requirement: A producer cannot emit a document its contract rejects
<!-- id: repo-004-02 -->
Producer functions SHALL validate what they built and raise rather than return
an invalid document. A decision builder SHALL validate the request it echoes.

#### Scenario: a builder is asked for an inconsistent decision

- **WHEN** an `assigned` decision is built without an `assignment`, or with a
  `reason` as well
- **THEN** the builder raises and names the offending path
- **AND** no document is returned to the caller

### Requirement: Decisions and receipts carry what makes them actionable
<!-- id: repo-004-03 -->
A capacity decision whose outcome is not `assigned` SHALL carry a typed
`reason` with a code from a closed enum. A receipt whose outcome is
`completed` SHALL carry an evidence digest. Under OD-001 (no commercial split
in Phase 1) no v1 schema SHALL declare a `tier`, `entitlement`, `license`, or
`paid` field, so a paid tier cannot influence a decision.

#### Scenario: a refusal arrives with no reason

- **WHEN** a decision has outcome `refused` or `unavailable` and no `reason`
- **THEN** validation fails and says the reason is required

#### Scenario: a completion is claimed without evidence

- **WHEN** a receipt has outcome `completed` and no `evidence`
- **THEN** validation fails; a completion claim without evidence is not a
  receipt

#### Scenario: a tier field is introduced

- **WHEN** any v1 schema declares a tier, entitlement, license, or paid field
- **THEN** the contract suite fails

### Requirement: The boundary's open-core import surface is pinned
<!-- id: repo-004-04 -->
The set of open-core modules imported by the `fleet-manager/` package SHALL be
declared and pinned by a test, so extraction has a bounded dependency rather
than a discovered one.

#### Scenario: a second core module is imported

- **WHEN** boundary code imports an open-core module outside the pinned set
- **THEN** the contract suite fails and names the new import
