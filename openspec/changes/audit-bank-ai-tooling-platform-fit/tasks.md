# Tasks

## 1. Audit the planning baseline

- [x] 1.1 Locate the November 25 v2.5 technical and leadership material with
  Work IQ and verify the supplied technical deck.
- [x] 1.2 Trace every planning section to a responsible layer and record
  current coverage and the required acceptance evidence.

## 2. Close engineering-governance gaps

- [ ] 2.1 Qualify a hosted reference workflow with pinned checks and evidence.
  Verify any private runner path separately before use. Track the reusable
  delivery contract in
  [`qualify-consumer-delivery-evidence`](../qualify-consumer-delivery-evidence/proposal.md).
- [ ] 2.2 Verify that required checks, reviewed source, an approved digest,
  and a recovery reference match at promotion. Use the proposed consumer
  evidence boundary in
  [`define-consumer-evidence-boundary`](../define-consumer-evidence-boundary/proposal.md)
  and the release-planning record in
  [`DG-22`](../dg22-prepare-approved-main-release/proposal.md) as upstream
  inputs; bank-side enforcement and acceptance remain open.
- [ ] 2.3 Rehearse single-writer recovery for monitoring and collect the
  resulting evidence within agreed recovery objectives, following
  [`qualify-monitor-recovery`](../qualify-monitor-recovery/proposal.md).

## 3. Qualify the bank-owned runtime

- [ ] 3.1 Exercise one Day 1 read-only tool against synthetic identities and
  records. Verify scoped identity, source permissions, default-deny behavior,
  durable evidence, and revocation against the proposed
  [`consumer evidence boundary`](../define-consumer-evidence-boundary/proposal.md).
- [ ] 3.2 Exercise a simulator for one explicitly approved change. Verify
  trusted policy, exact approval, credential scope, idempotency, uncertain
  outcome reconciliation, and no duplicate effects. Keep program effects
  under the bank-owned authorization boundary.
- [ ] 3.3 Verify tenant entitlements, policy coverage, operations, recovery,
  and deployment acceptance with their accountable owners. Activate optional
  products and a central gateway only after their separate decisions.

## Accountable roles and next receipts

The source handoff identifies accountable functions, not named individuals.
These assignments preserve that role-level ownership; each task remains open
until its acceptance evidence is recorded.

| Task | Accountable owner roles | Next acceptance receipt |
| --- | --- | --- |
| 2.1 Hosted reference workflow | Consumer CI owner and release owner | Review the [synthetic hosted pilot](../qualify-consumer-delivery-evidence/hosted-pilot.md) and supply the corresponding bank-selected runner, tool pin, positive and rejection receipts for bank acceptance. |
| 2.2 Promotion evidence | Consumer CI owner and release owner | Protected-path evidence that required checks, reviewed source, approved artifact digest, approval, recovery reference, and rollback decision match at promotion. |
| 2.3 Monitor recovery | Monitor maintainer and operator | Rehearsal receipt for restore, writer fencing, heartbeat reconciliation, and alert continuity against agreed recovery objectives. |
| 3.1 Read-only runtime pilot | Runtime owner and data owner | Synthetic identity and record results for scoped access, source permissions, default-deny, durable evidence, and revocation for one named tool. |
| 3.2 Controlled action pilot | Action owner, identity owner, and target owner | Simulator receipt for exact approval and parameters, credential scope, idempotency, uncertain-outcome reconciliation, and accepted/denied effect counts. |
| 3.3 Operational acceptance | Tenant owner, security owner, and platform owner | Tenant entitlement and policy results plus deployment, operations, and recovery acceptance for selected services; keep bank-controlled receipts with the bank. |
