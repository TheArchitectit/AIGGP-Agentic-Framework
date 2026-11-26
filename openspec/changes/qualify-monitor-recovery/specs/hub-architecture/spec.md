## ADDED Requirements

### Requirement: Monitor backups describe a complete state generation
<!-- id: mon-recovery-01 -->
The monitor SHALL manifest the configured runner registry, service map, and
append-only alert records as one consistent generation. It SHALL record each
member's normalized path, byte count, applicable schema version, and SHA-256, plus
an archive digest. A detached manifest digest SHALL cover canonical manifest
content with the digest field omitted.

#### Scenario: A complete state generation is backed up
- **WHEN** the monitor is quiesced and every required state file matches its declared schema
- **THEN** the backup includes the complete generation and a digest-verifiable manifest

#### Scenario: Backup inputs are missing or unsafe
- **WHEN** a required state file is missing, a path escapes the configured data directory, a path is duplicated, or a digest cannot be verified
- **THEN** backup creation fails without reporting a valid backup

### Requirement: Monitor backups exclude deployment secrets
<!-- id: mon-recovery-02 -->
Backup files SHALL remain private instance artifacts and SHALL NOT contain
environment secrets or plaintext bearer tokens. Public examples and receipts SHALL
NOT expose live deployment identifiers or private instance values.

#### Scenario: A backup is prepared for private storage
- **WHEN** monitor state is packaged for backup
- **THEN** credentials and environment secrets are excluded and the artifact is not added to the repository

### Requirement: Recovery validates state before replacement
<!-- id: mon-recovery-03 -->
The monitor SHALL verify the complete manifest, file digests, and applicable
schemas in staging before replacing live state. A failed restore SHALL leave the
prior live state unchanged.

#### Scenario: A verified backup restores
- **WHEN** every staged file passes manifest, digest, and schema validation
- **THEN** the complete staged generation replaces the live state as one restore operation

#### Scenario: Invalid backup cannot partially replace state
- **WHEN** any archive file is missing, malformed, unsupported, unsafe, or has a mismatched digest
- **THEN** restore fails, the original live state remains byte-for-byte unchanged, and no convergence receipt is issued

### Requirement: Unreconciled runners remain unknown after restore
<!-- id: mon-recovery-04 -->
Restored runner records SHALL remain unknown until authenticated heartbeat
reconciliation succeeds. Records with missing or rejected credentials SHALL
require explicit re-enrollment and SHALL NOT be reported healthy by default.

#### Scenario: A restored runner cannot authenticate
- **WHEN** a restored runner has no usable credential or its heartbeat is rejected
- **THEN** the monitor marks that runner unknown and requires explicit re-enrollment before it can count as reconciled

### Requirement: Recovery preserves one writer and proves convergence
<!-- id: mon-recovery-05 -->
The monitor SHALL hold an exclusive state-directory lock before loading or writing
state. Restore SHALL fence the prior writer and advance a durable writer generation.
Receipts SHALL record the manifest and file digests, schema version, writer
generation, and non-identifying record counts. Convergence SHALL be reported
separately from integrity-verified state restore.
This requirement preserves one writer and SHALL NOT imply high availability or
automatic failover.

#### Scenario: A second writer cannot claim the state directory
- **WHEN** another monitor process holds the exclusive state-directory lock
- **THEN** the new process exits before loading or mutating the registry, services, or alert history

#### Scenario: Recovery cannot fence the prior writer
- **WHEN** restore cannot acquire exclusive ownership or cannot advance the durable writer generation
- **THEN** restore aborts without replacing live state or issuing a restored or convergence receipt

#### Scenario: Restored state has not converged
- **WHEN** any non-deferred enrolled runner remains stale, unknown, or pending re-enrollment, or alert deduplication is unresolved
- **THEN** no convergence receipt is issued and the missing state is not reported healthy

#### Scenario: State integrity succeeds before runner convergence
- **WHEN** restored files pass integrity checks but a non-deferred enrolled runner has not reconciled
- **THEN** the monitor may issue a state-restored receipt but SHALL NOT issue a convergence receipt
