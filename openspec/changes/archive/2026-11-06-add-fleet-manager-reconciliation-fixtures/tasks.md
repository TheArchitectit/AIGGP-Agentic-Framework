# Tasks: add-fleet-manager-reconciliation-fixtures

Program package: `devgate-product-tiers-fleet-manager`, Sprint 2 box 2.3
(deterministic reconciliation fixtures — FLEET-003). Predecessors:
`add-fleet-manager-domain-models` (2.1), `add-fleet-manager-plan-apply` (2.2).

## 1. The diff

- [x] 1.1 `fleet_manager/reconcile.py` — `reconcile()` comparing one
      `DesiredState` revision with one `Observation` per host, returning a
      `Reconciliation` (drifts, candidates, submitted changes, deferrals)
- [x] 1.2 `Reconciliation` recomputes its id from `(revision, reports, limits,
      halted)` and refuses a mismatch; drifts are held in their total order and
      `changes` must be the candidates that were not deferred
- [x] 1.3 Drift kinds: `warm_shortfall`, `unmanaged_runner`, `unknown_host`,
      `host_not_reporting`, `drain_completable`, `drain_blocked`
- [x] 1.4 The only candidates are `assign` (warm floor) and `complete_drain`
      (nothing left); counts per (host, pool), never an invented runner id

## 2. Bounded convergence

- [x] 2.1 `ConvergenceLimits` — drains, replacements, host mutations; zero is
      the expression of a halted reconciler
- [x] 2.2 `bound_candidates()` — charges every candidate against the three caps
      and the affected pools' `DisruptionBudget.max_parallel`; a deferral names
      the cap that was reached, and every candidate is submitted or deferred,
      never both
- [x] 2.3 `halted=True` submits nothing and preserves the whole diff

## 3. Evidence

- [x] 3.1 `tests/fixtures/reconcile/cases.json` — nine fixtures, hand written
      expectations, including the halted twin of the bounded case
- [x] 3.2 `tests/test_reconcile_v1.py` — 29 tests, floor-pinned to this module;
      the fixture document is compared exactly, and the id is recomputed in two
      subprocesses with different hash seeds
- [x] 3.3 `docs/qa/2026-10-24-fleet-manager-reconciliation-fixtures.md` —
      planted mutations, the gate table, and the stated limits
