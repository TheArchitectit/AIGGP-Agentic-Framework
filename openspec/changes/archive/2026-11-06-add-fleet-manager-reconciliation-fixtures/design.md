# Design: Fleet Manager reconciliation fixtures

## The diff is a value with an id, and the id is over the inputs

`reconciliation_id_for(revision, observations, limits, halted)` hashes exactly
those four things — not the drifts, not the changes. The drifts are derived; if
the id covered them, a bug in the diff would bless itself. Covering the inputs
means two reconcilers that read the same revision and the same reports under
the same caps agree on the id, and one of them changing its output shows up as
the same id with a different document, which is a failure a fixture can catch.

`Reconciliation.__post_init__` recomputes the id and refuses a mismatch. It also
enforces the shape of the value: drifts in their total order, and `changes` as
the candidates that were not deferred, in candidate order. Both are properties
of a diff rather than of a caller, so they belong to the type.

## Ordering is a total order, never iteration order

Every list in the document is ordered by a key spelled out in the code:

- drifts by `(kind, host_id, pool_id)`;
- candidates by `(kind priority, subject, parameters)`, where the priority
  finishes disruptions already in motion (`complete_drain`, `return_to_service`,
  `drain`) before it starts new ones and places `assign` last;
- the shortfall's placement by `(-free_slots, host_id)`, so the tie goes to the
  lower id and the next slot to the host with more room.

There is no set iteration in any of these paths. The suite proves it from
outside as well: a subprocess runs every fixture under two different
`PYTHONHASHSEED` values and compares the ids.

## Bounded convergence is a function over changes

`bound_candidates()` takes any `Change` values and splits them into what may be
submitted now and what waits. Each change is charged against up to four limits:

- `ConvergenceLimits.max_drains` — `drain` and `complete_drain`;
- `ConvergenceLimits.max_replacements` — `rollout`;
- `ConvergenceLimits.max_host_mutations` — any change that names a host;
- the affected pool's `DisruptionBudget.max_parallel`, for destructive changes
  only, and charged to *every* pool a host may serve, because a drain disturbs
  all of them.

A deferred change carries the change and the reason, and the reason names the
exact cap that was reached. A cap of zero is meaningful: it is how "a halted
reconciler submits nothing" is expressed in data, and the diff is still
returned, which is the part of FLEET-003's loss-of-manager clause that a value
can hold.

## The reconciler only acts where it can prove the state

The candidates are deliberately few:

- `assign` when a pool's active reporting hosts run fewer runners than
  `warm_min`, placed only on hosts that reported and have free slots;
- `complete_drain` when a draining host has no assignment *and* its report
  shows no runner.

Everything else is a drift and nothing more. A runner the desired state does not
account for is `unmanaged_runner` and is left alone, even when it has no job —
the reconciler has no evidence about what it is, and killing it is how a warm
pool loses a job it never saw. A host that has not reported is
`host_not_reporting` and receives no assignment, because placing work on a host
whose state is unknown is how a reconciler creates load it cannot see. An
unknown host's report is `unknown_host` and is not adopted. A drain with
assignments or runners left is `drain_blocked`, with the counts.

## Assignments and runners are matched by count, not by id

`Assignment` carries an `assignment_id` minted by the manager and a `request_id`
from the core. `ObservedRunner` carries a `runner_id` minted on the host. There
is no shared instance key at v1, so the diff compares counts per (host, pool).
Inventing an identity here would put a join in code that neither contract
promises, and the first time a host restarted a runner the join would be wrong.

## Reconciliation-placed assignments name the reconciler

A reconciler-placed assignment answers no core request. Its `assignment_id` is
`rec.<pool>.<n>` and its `request_id` is `reconcile.<pool>.<n>`, where `n` is the
lowest free index for that pool in the current state. Both are derived from the
state, so the same state produces the same ids, and a partially converged pool
does not collide with the assignment the last run placed.

## Not in this change

No observation store, no staleness policy (a report is used as given, and its
`observed_at` is carried into the id), no runtime action, no release, drain or
rollout candidate, and no scheduler. The reconciler is a function from a
revision and a set of reports to a diff; who calls it, and how often, is the
API's business (Sprint 7).
