# Tasks

## 1. Bound the persisted state

- [x] 1.1 Inventory the versioned registry/service-map schemas and append-only alert
  records; identify the exact configured files and exclude runtime secrets and
  deployment configuration from the backup set. See the [source and fixture inventory](state-inventory.md).
- [ ] 1.2 Define strict manifest and receipt schemas with normalized relative paths,
  schema versions, byte counts, SHA-256 digests, writer generation, and
  privacy-safe runner counts.

## 2. Implement backup and controlled restore

- [ ] 2.1 Produce a consistent generation of registry, service-map, and alert-log
  state with a manifest; reject incomplete or unsafe inputs and verify archive
  digests before use.
- [ ] 2.2 Stage and validate restores before replacing live state; prove malformed,
  incomplete, unsupported-schema, and digest-mismatch inputs leave the prior state
  unchanged.
- [ ] 2.3 Preserve only hashed heartbeat credentials. Record restored runners as
  unknown until authenticated heartbeat reconciliation; require explicit
  re-enrollment for missing or rejected credentials.

## 3. Fence the writer and prove recovery

- [ ] 3.1 Add an exclusive state-directory writer lock and durable monotonic writer
  generation. Prove a second writer and a restore with an unfenced writer fail
  before loading or changing state.
- [ ] 3.2 Emit a state-restored receipt only after manifest, schema, and file
  integrity checks pass. Emit a separate convergence receipt only after every
  expected runner and open-alert deduplication state is reconciled.
- [ ] 3.3 Add positive disposable fixtures for successful restore and convergence,
  plus negative fixtures for corruption, unsafe paths, lock contention, stale
  runners, and required re-enrollment. Assert that failures preserve the source
  state and receipts contain no secrets or private instance data.
- [ ] 3.4 Independently review the implementation and fixtures; run strict OpenSpec
  validation and traceability. Keep the one-monitor boundary and avoid any HA,
  automatic failover, or live deployment claim.
