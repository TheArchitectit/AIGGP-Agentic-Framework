# Sprint plan — DG-02 hub and integration gaps

Use the [sprint dispatch guide](../../SPRINTS.md) with this package’s [tasks](tasks.md), [proposal](proposal.md), and [batch 007 review](../dg-02-evidence-ledger-reconciliation/batches/batch-007/README.md).

Exercise the native entry point for this change. A change to session startup or manifest handling also needs a carrier-specific receipt. [Session adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Roles

- Lead: approve scope and safety boundary, reconcile evidence, and sign off.
- Luna: implement controlled fixtures and collect local/CI behavior receipts.
- Independent auditor: separate session checks fixtures, results, deployment assumptions, and row bundles.
- Accountable owners: monitor hub maintainer, deployment operator, integration consumer policy owner, and DG-02 evidence owner.

## S1 — intake and baseline

- Treat batch 007 findings for rows 073–084 as current evidence leads; they do not establish historical closure.
- Map tasks 1.1–1.3 to listener policy; 2.1–2.4 to `mon-hub-01`, `mon-channels-01`, `mon-registry-01`, `mon-deadman-01`; 3.1–3.4 to `coh-int-01..07`; task 3.5 to evidence/state gating.
- Record intended single-hub topology, configured local-network policy, tested environments, and owners for real listener/firewall observations.
- Exit when allowed local address policy and integration test boundary are agreed; no live deployment is assumed.

## S2 — implementation and evidence

- Tasks 1.1–1.2: define and enforce loopback/configured-LAN behavior, resolution changes, and fail-closed invalid/public/wildcard handling across address families using controlled fixtures.
- Task 1.3: update operational docs and obtain operator evidence for listener and firewall assumptions in an authorized controlled environment.
- Tasks 2.1–2.4: exercise one-hub configuration, heartbeat-only status, registry placement/data hygiene, and watchdog failure/hosted-runner exclusion.
- Tasks 3.1–3.4: compare immutable local/CI outputs, preserve fleet metadata, qualify consumer promotion/advisory semantics, timeout/skip propagation, multi-repo and watched-branch cases.
- Task 3.5: bind per-row result and provenance, seal accepted findings, and keep unsupported claims UNPROVEN.

## S3 — independent qualification

- Auditor reviews the listener policy against actual config and replays defensive address/heartbeat/integration fixtures.
- Auditor checks real-environment statements have operator-owned receipts; fixtures cannot stand in for firewall or deployment evidence.
- Auditor validates row-specific bundles and expected digests; lead sends only complete transitions to the state gate.

## S4 — integration and closeout

- Run hub/integration suites, strict OpenSpec, traceability, evidence validator, and state gate at the final reviewed commit.
- Handoff: policy, fixture matrix, local/CI comparison, any operator receipt, per-row digest map, auditor verdict, and deployment limits.
- Close only accepted evidence; preserve the one-hub model and make no HA or production-readiness claim.
