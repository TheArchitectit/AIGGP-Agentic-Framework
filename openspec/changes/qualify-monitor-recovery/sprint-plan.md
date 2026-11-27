# Sprint plan — monitor recovery under single-writer ownership

Use the [sprint dispatch guide](../../SPRINTS.md) with this package’s [tasks](tasks.md), [proposal](proposal.md), [design](design.md), and [state inventory](state-inventory.md).

Exercise the native entry point for this change. A change to session startup or manifest handling also needs a carrier-specific receipt. [Session adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Roles

- Lead: own recovery contract/design and review; sign off on the one-monitor boundary.
- Luna: implement disposable backup/restore fixtures and collect reproducible receipts.
- Independent auditor: separate session verifies source preservation, lock/generation behavior, receipt privacy, and test results.
- Accountable owners: monitor maintainer owns formats and code; operator owns controlled recovery assumptions and evidence.

## S1 — intake and baseline

- Accept task 1.1 and `state-inventory.md` as the completed inventory of registry, service map, alert history, and excluded runtime secrets/configuration.
- Map tasks 1.2 to versioned manifest/receipt schemas; tasks 2.1–2.3 to backup, staged restore, and credential reconciliation; tasks 3.1–3.4 to fencing, receipts, fixtures, and independent review.
- Record existing file formats, writer paths, configured directories, and which sources require quiescence; keep private instance data outside committed examples.
- Exit when schema fields, normalized path rules, privacy limits, and single-writer ownership are agreed.

## S2 — implementation and evidence

- Task 1.2: define strict versioned manifest/receipt shapes, normalized relative paths, byte counts/digests, writer generation, and privacy-safe counts.
- Tasks 2.1–2.2: produce consistent backups, verify digests, stage restore, and prove malformed/incomplete/unsupported/mismatched inputs preserve prior state.
- Task 2.3: preserve only credential hashes; require authenticated heartbeat reconciliation and explicit re-enrollment for missing/rejected credentials.
- Tasks 3.1–3.2: enforce exclusive writer lock/monotonic generation before state load or mutation; emit separate restored and convergence receipts only after their criteria pass.
- Task 3.3: cover success, corruption, unsafe paths, lock contention, stale runners, and re-enrollment with disposable data; assert source preservation and receipt privacy.
- Exit without any claim of a live restore or deployment.

## S3 — independent qualification

- Auditor replays fixture suite, checks hashes and byte-for-byte failure preservation, and confirms lock refusal occurs before state changes.
- Auditor inspects receipts and archives for secrets, private identifiers, and confusion between restored and converged status.
- Lead reconciles findings and keeps any unverified runtime/operator assumption explicitly open.

## S4 — integration and closeout

- Task 3.4: run strict OpenSpec and traceability; review implementation and fixtures independently while preserving the single-monitor boundary.
- Handoff: schema versions, fixture matrix, digest and lock receipts, privacy review, auditor verdict, strict/traceability results, and operator limitations.
- Avoid HA, automatic failover, second-writer service, or live deployment claims; archive only when task evidence supports it.
