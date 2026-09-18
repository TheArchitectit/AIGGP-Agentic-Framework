# Tasks: devgate-product-tiers-fleet-manager

Status: PROPOSED — BLOCKED. Every task below is blocked by
devgate-spec-coherence-service acceptance (DEP-001). This file records the
sprint plan from the package's section 12; it is documentation, not a work
authorization. Full normative text: proposal.md in this directory.

## 0. Dependency lock (Sprint 0 entry)

- [ ] 0.1 Predecessor devgate-spec-coherence-service accepted: sealed identity, green required gates from clean clone, docs/qa/ acceptance record with exact commit (DEP-001)
- [ ] 0.2 Fresh full-repository audit at new head; docs/qa/YYYY-MM-DD-product-tiers-fleet-manager-baseline.md published (DEP-003)
- [ ] 0.3 Predecessor identity imported; dependency-review record confirms no contract redefined here
- [ ] 0.4 Overlaps reconciled with runner-monitoring, enrollment-and-alerting, hub-architecture, add-runner-to-fleet
- [ ] 0.5 Owner decisions OD-001 (commercial license text) and OD-002 (enterprise/ vs fleet-manager/ root) resolved

## 1. Sprint 1: repository and contract gates

- [ ] 1.1 Commercial boundary + license manifest; dependency-direction and changed-path license gates
- [ ] 1.2 Versioned contracts/v1 + bidirectional contract tests; entitlement isolation tests
- [ ] 1.3 Extraction rehearsal in CI; core gates proven green with commercial code absent

## 2. Sprint 2: Fleet Manager domain and desired state

- [ ] 2.1 Repository, host, pool, assignment, capacity, drain, rollout models (FLEET-001)
- [ ] 2.2 Plan/apply with revisions and idempotency (FLEET-002); audit events; API authn/authz skeleton
- [ ] 2.3 Deterministic reconciliation fixtures

## 3. Sprint 3: host agent and signed configuration

- [ ] 3.1 Outbound host-agent channel; enrollment, rotation, signature verification, replay protection (FLEET-004)
- [ ] 3.2 Operation allowlist + receipts (no remote shell); runner-enroll.sh compatibility or migration
- [ ] 3.3 Failure and revocation fixtures; two test hosts reconcile signed no-op desired state

## 4. Sprint 4: Docker and Podman ephemeral adapters

- [ ] 4.1 Stable adapter contract; pinned ephemeral runner image; warm-pool behavior
- [ ] 4.2 One-job lifecycle, cleanup proof, quarantine, resource limits, typed errors (RUN-001, RUN-002)
- [ ] 4.3 Controlled jobs complete on Docker and Podman with destroyed job environments and complete receipts

## 5. Sprint 5: secret subsystem

- [ ] 5.1 Provider adapter selected (OD-003) and implemented; provider-neutral lease interface (SEC-*)
- [ ] 5.2 Just-in-time registration and job credentials; protected injection
- [ ] 5.3 Redaction, canaries, rotation, revocation, outage behavior; secret classes segregated

## 6. Sprint 6: second host, dell-u2 drain, and failover

- [ ] 6.1 Second physical host enrolled; required Phase 1 pools distributed (RUN-004)
- [ ] 6.2 Drain and disruption budgets; full failover exercise executed (RUN-003)
- [ ] 6.3 Recovery and rollback proven; evidence filed under docs/qa/

## 7. Sprint 7: onboarding portal and API

- [ ] 7.1 Repository discovery and plan; pool/group assignment and workflow proposal automation (ONB-001, ONB-002)
- [ ] 7.2 Partial-resume and rollback
- [ ] 7.3 Controlled verification run reaches intended pool with non-vacuous gates (ONB-003)

## 8. Sprint 8: evidence-plane paid services

- [ ] 8.1 Tier-independent core fixture; byte-identical decisions across entitlements (TIER-001)
- [ ] 8.2 Detached aggregation and retention; control mappings, approvals, exports (TIER-002, TIER-003)
- [ ] 8.3 Entitlement failure and commercial-service outage tested

## 9. Sprint 9: MissionControl presentation

- [ ] 9.1 Read-only views with source/freshness; mediated commands with authoritative receipts (INT-001, INT-002)
- [ ] 9.2 MissionControl loss has no effect on source state
- [ ] 9.3 rad-gateway verified absent from the trust path (INT-003)

## 10. Sprint 10: ARC adapter, deferred

- [ ] 10.1 Entry gate: Sprints 0-9 accepted and Phase 1 stable (OD-007)
- [ ] 10.2 ARC adapter via supported interfaces; no ARC internals reimplemented

## 11. Sprint 11: release acceptance

- [ ] 11.1 Clean-clone build and full gates; contract compatibility and extraction rehearsal
- [ ] 11.2 Security, failover, restore, rollback, and entitlement-isolation tests
- [ ] 11.3 docs/qa/ release record with exact SHA, commands, runs, evidence, known limits, rollback versions
