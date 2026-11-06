# Tasks: add-fleet-manager-plan-apply

Program package: `devgate-product-tiers-fleet-manager`, Sprint 2 box 2.2
(plan/apply with revisions and idempotency — FLEET-002; audit events; API
authn/authz skeleton). Predecessors: `add-fleet-manager-domain-models` (2.1).

## 1. Plan

- [x] 1.1 `fleet_manager/plan.py` — `Change` (one intended operation),
      `Plan` (identity = digest of base revision + ordered changes, computed
      capacity impact, destructive flag), `build_plan()` simulating every
      change and refusing an impossible one with its index
- [x] 1.2 The plan clock derived from the state (`plan_clock`), so a plan is
      reproducible per revision and cannot simulate a transition before the
      work it acts on
- [x] 1.3 A plan's identity is recomputed on construction, so an edited plan is
      refused rather than applied

## 2. Apply, idempotency, audit, authorization

- [x] 2.1 `fleet_manager/apply.py` — `apply_plan()` bound to the planned
      revision, revalidating every change against the real state and time;
      `IdempotencyLedger` (append-only, key → plan → resulting revision)
- [x] 2.2 `fleet_manager/audit.py` — `AuditLog` / `AuditEvent`: frozen,
      contiguous `1..n`, non-decreasing time, reasons that cannot carry a
      credential; a plan's entries committed only if the whole plan applied
- [x] 2.3 `fleet_manager/auth.py` — `Principal`, `Scope`, the written-out ladder
      read < plan < apply < admin; destructive applies require `fleet.admin`
- [x] 2.4 A refusal is a value: `ApplyRefused.audit_log` carries the entry that
      records it

## 3. Evidence

- [x] 3.1 `tests/test_plan_apply_v1.py` — 44 tests, floor-pinned to this module;
      every requirement's scenarios as named tests, including the two defects a
      second read found (the sentinel clock, the non-atomic audit entries)
- [x] 3.2 `docs/qa/2026-10-24-fleet-manager-plan-apply.md` — planted mutations,
      the gate table, and what this deliberately does not do
