# Sprint plan — bank AI tooling platform fit

**Scope:** qualification planning for the six open task lanes in v2.5; this audit found no production deployment or entitlement evidence.
Tasks 1.1–1.2 establish the planning baseline only. No bank-side work is assigned until the accountable owner agrees to a synthetic pilot and its scope.

## Sequence

### S1 — intake/baseline

- Confirm the November 25 v2.5 deck, source revisions, Day 1 scope, owner roles, and receipt criteria in `bank-platform-fit.md`.
- Preserve the six task lanes and their role-level accountability; no individual owners were identified.

### S2 — implementation or evidence collection (six separate owner lanes)

- **2.1 hosted reference workflow — Consumer CI owner + release owner:** on selection, review the synthetic hosted pilot; provide bank-selected runner/tool pin and positive/rejection receipts. Verify any private runner path separately before use.
- **2.2 promotion evidence — Consumer CI owner + release owner:** prove required checks, reviewed source, approved digest, approval, recovery reference, and rollback decision match at promotion; depend on the consumer boundary and DG-22 inputs.
- **2.3 monitor recovery — Monitor maintainer + operator:** rehearse single-writer recovery, writer fencing, heartbeat reconciliation, and alert continuity against agreed recovery objectives.
- **3.1 read-only pilot — Runtime owner + data owner:** exercise one Day 1 tool on synthetic identities/records; prove scoped access, source permissions, default deny, durable evidence, and revocation.
- **3.2 controlled action pilot — Action owner + identity owner + target owner:** use a simulator for one explicitly approved change; prove exact approval/parameters, scoped credential, idempotency, uncertain-outcome reconciliation, and no duplicate effects.
- **3.3 operational acceptance — Tenant owner + security owner + platform owner:** verify entitlements, policy, operations, recovery, and deployment for selected services; activate optional products/gateway only after their separate decisions.

### S3 — independent qualification

- A distinct audit session checks each lane’s receipt against its acceptance criteria and rejects synthetic evidence presented as production acceptance.
- Record missing proof against the affected lane. A simulator is required for task 3.2, recovery objectives belong to 2.3 and 3.3, and the relevant bank owner accepts each lane’s evidence.

### S4 — integration/closeout

- Lead composes only the accepted lane results; each accountable bank owner retains its own receipt and signs off its own control boundary.
- Launch readiness depends on required Day 1 controls, not every optional phase. No deployment or entitlement is inferred from the upstream package.

## Bounded roles

- Lead: maintain cross-lane dependencies, review, and sign-off. Luna: prepare evidence templates and collect only owner-authorized synthetic receipts. A separate audit session qualifies them independently.

## Sources

- [Proposal](proposal.md) · [Tasks, owner roles, and next receipts](tasks.md) · [Bank platform fit assessment](bank-platform-fit.md)
- [Consumer evidence boundary](../define-consumer-evidence-boundary/proposal.md) · [Global sprint plan](../../SPRINTS.md)

Use the package’s native acceptance path. If the session interface changes, assign its carrier-specific work through the [five-adapter matrix](../../SPRINTS.md#session-adapter-matrix).
