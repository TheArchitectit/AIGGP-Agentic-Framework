# Secret Rotation

## ADDED Requirements

### Requirement: Scrubbing a secret from HEAD is not revoking it
<!-- id: sr-01 -->
A detection recorded as removed from `HEAD` but not revoked at the provider MUST fail the
gate once past the revocation window. Removing a value from the working tree neither
revokes the credential nor removes it from reachable history, so a scan-clean repository
can still hold a live secret.

#### Scenario: scrubbed but never revoked
- **WHEN** a key was removed from HEAD 65 days ago and the ledger records no revocation
- **THEN** the gate fails naming the item and stating that scrubbing is not revocation

#### Scenario: still committed
- **WHEN** a detection older than the window is not recorded as removed from HEAD
- **THEN** the gate fails stating the secret remains in the tree

### Requirement: A revocation must carry date and evidence
<!-- id: sr-02 -->
A row marked revoked MUST include both a `revoked_at` date and an `evidence` pointer to
the revocation record. An unrecorded revocation MUST fail, because it is indistinguishable
from a claimed one.

#### Scenario: claimed revocation with no record
- **WHEN** a ledger row sets `revoked: true` with neither `revoked_at` nor `evidence`
- **THEN** the gate fails naming both missing fields

#### Scenario: revocation with a pointer
- **WHEN** a row carries `revoked_at` and an evidence reference such as a console record id
- **THEN** the gate passes for that row

### Requirement: A malformed row cannot be partially trusted
<!-- id: sr-03 -->
A ledger row missing any required field MUST fail immediately rather than being skipped or
defaulted. A row the gate cannot fully parse MUST NOT contribute a passing state.

#### Scenario: missing required field
- **WHEN** a ledger line omits `family`
- **THEN** the gate fails naming the line and the missing field

### Requirement: An empty ledger passes; an unparseable one does not
<!-- id: sr-04 -->
An empty ledger MUST pass, because no detections have been recorded yet. A non-empty
ledger from which no rows parse MUST fail with the nothing-scanned code, since it cannot
distinguish "no detections" from "unreadable ledger".

#### Scenario: empty file
- **WHEN** the ledger file exists but is empty
- **THEN** the gate passes stating no detections are recorded

#### Scenario: comments only
- **WHEN** the ledger contains only comments and blank lines
- **THEN** the gate refuses with a vacuous-pass message rather than reporting a clean state
