# Change: Fleet Manager reconciliation fixtures

## Why

Sprint 2.2 can carry out a plan, but nothing yet decides *which* plan the
observed world calls for. FLEET-003 is about that decision and about its two
failure modes. A reconciler that tries to converge everything at once turns one
incident into a fleet-wide one, so convergence has to be bounded by declared
caps and by each pool's disruption budget. A reconciler that acts on a report it
cannot interpret completes a drain over a runner that is still running a job, so
it has to be explicit about what it refuses to touch. Neither property survives
if the diff is not deterministic: a fixture that cannot be asserted byte for
byte is not evidence.

## What changes

- `fleet-manager/fleet_manager/reconcile.py` — `reconcile()`, which diffs one
  `DesiredState` revision against one `Observation` per host and returns a
  `Reconciliation`; `bound_candidates()`, the FLEET-003 caps and disruption
  budgets as a function over `Change` values; `ConvergenceLimits`, `Drift`,
  `Deferred`, and the observation document form the fixtures are written in.
- `fleet-manager/tests/test_reconcile_v1.py` — 29 tests, floor-pinned to this
  module.
- `fleet-manager/tests/fixtures/reconcile/cases.json` — nine fixtures with hand
  written expectations, including the version of each case with the reconciler
  halted.

`Reconciliation.changes` are `plan.Change` values, so the output of a reconcile
is an input to `plan.build_plan()` and to `apply.apply_plan()` unchanged. The
reconciler never produces a revision itself.

## What this does not change

No runtime contact, no adapter calls, no host agent, no persistence of
observations, and no staleness policy for a report. It does not release, drain
or replace anything: those candidates arrive with the sprints that can prove a
runner finished. The join between assignments and runners is by (host, pool)
count, because the contracts carry no shared instance id.
