# QA record: Fleet Manager reconciliation fixtures (Sprint 2.3)

Scope: `devgate-product-tiers-fleet-manager` box 2.3, "deterministic
reconciliation fixtures" (FLEET-003, bounded convergence). AIGGP change
`add-fleet-manager-reconciliation-fixtures`, requirements `fleet-003-01..04`.

## What landed

- `fleet-manager/fleet_manager/reconcile.py` — `reconcile()`, `Reconciliation`,
  `ConvergenceLimits`, `Drift`, `Deferred`, `bound_candidates()`, and the closed
  report form (`observation_from_document` / `observation_to_document`).
- `fleet-manager/tests/fixtures/reconcile/cases.json` — nine fixtures, data, with
  hand written expectations.
- `fleet-manager/tests/test_reconcile_v1.py` — 29 tests, floor-pinned to this
  module.

A reconciliation is a value. It carries drifts (what differs), candidates
(every change it considered), changes (the candidates it submits) and deferrals
(the candidates it did not, each with the cap that stopped it). Its id is a
digest of exactly `(base_revision, observations, limits, halted)` and is
recomputed on construction, so an edited diff is refused. Its changes are
`plan.Change` values, which means a reconcile is an input to `build_plan()` and
`apply_plan()` unchanged; this module never produces a revision itself.

## The decision that shaped the rest: counts, not instance ids

`Assignment` carries `assignment_id` (minted by the manager) and `request_id`
(from the core). `ObservedRunner` carries `runner_id` (minted on the host).
There is no shared instance key at v1, so the diff compares *counts per (host,
pool)*. A join on ids would be a join on nothing, and it would break the first
time a host restarted a runner under the same name -- the exact event
reconciliation exists to notice.

## What the reconciler will and will not do

Candidates, in full:

- `assign` when a pool's active reporting hosts run fewer runners than
  `warm_min`, placed only on hosts that reported and have free slots;
- `complete_drain` when a draining host has no desired assignment *and* no
  reported runner.

Everything else is a drift and no change:

- `unmanaged_runner` -- a reported runner no assignment accounts for, with or
  without a job. Left alone even when idle: the reconciler has no evidence what
  it is, and killing it is how a warm pool loses a job it never saw.
- `host_not_reporting` -- an active host with no observation gets no new
  assignment, because placing work on a host whose state is unknown is how a
  reconciler creates load it cannot see.
- `unknown_host` -- a report from a host not in the desired state is reported,
  never adopted.
- `drain_blocked` -- a draining host with assignments or runners left, with
  both counts named.
- `warm_shortfall` -- reported with its count even when no host can take the
  work (for example, the only host is draining).

Two reports for one host are refused rather than merged: deciding which is
newer is not this layer's guess.

## Fixtures

Nine cases, each a desired-state document, the reports, the limits and the halt
state, with expected drifts, changes and deferrals written by hand and compared
exactly, in order:

| Case | What it pins |
| --- | --- |
| `converged` | nothing to do, nothing reported |
| `warm-shortfall` | two slots short, two assignments placed |
| `bounded-by-host-mutations` | three short, cap two: the third deferred with the cap named |
| `halted` | the same diff, zero submitted, every candidate deferred with the halt |
| `unmanaged-runner-is-left-alone` | two unaccounted runners (one with a job), untouched |
| `drain-completable` | nothing left: one `complete_drain`; no assignment to a draining host |
| `drain-blocked-by-observed-runner` | a reported runner blocks the drain |
| `placement-spreads-across-hosts` | tie to the lower id, next slot to the host with more room |
| `silent-host-gets-no-assignment` | a silent host is reported and gets no work |

Determinism is asserted two ways: the fixture document is compared byte for
byte across runs in-process, and a subprocess reconciles every fixture under
`PYTHONHASHSEED=0` and `=1` and compares the ids. Ordering everywhere is a
spelled-out total order (drifts by `(kind, host, pool)`, candidates by
`(kind priority, subject, parameters)`, placement by `(-free slots, host id)`);
no set iteration feeds any list.

## Planted mutations: 13/13 killed

| # | Mutation | Killed by |
| --- | --- | --- |
| M1 | a halted reconciler keeps submitting | fixture comparison (`halted`) |
| M2 | drain cap not enforced | `test_the_drain_cap_defers_the_rest` |
| M3 | host-mutation cap not enforced | `test_a_zero_cap_submits_nothing...`, fixture |
| M4 | pool disruption budget not enforced | `test_a_pool_disruption_budget_caps_destructive_changes` |
| M5 | a draining host's runners count as warm capacity | fixture comparison (`drain-blocked`) |
| M6 | a silent host may receive an assignment | `test_a_silent_host_gets_no_assignment`, fixture |
| M7 | drifts may be held out of their total order | `test_drifts_out_of_their_total_order_are_refused` |
| M8 | the id ignores the halt state | `test_the_id_is_a_digest...` |
| M9 | changes need not be the kept candidates | `test_changes_must_be_the_candidates...`, fixture |
| M10 | an unknown field in a report is accepted | `test_an_unknown_field_is_refused` |
| M11 | an unmanaged runner is released | `test_an_unmanaged_runner_is_reported_and_left_alone`, fixture |
| M12 | placement prefers the busiest host | fixture comparison (`placement-spreads-across-hosts`) |
| M13 | the batch is charged in generation order, not its total order | `test_a_batch_with_two_kinds_is_submitted_in_its_documented_order` |

## Defects found while building this slice

**A state with two kinds of candidate could not be reconciled at all.** The
candidate list was built in generation order -- warm shortfalls per pool first,
drains afterwards -- while `bound_candidates()` submits in the documented total
order, which finishes disruptions in motion (`complete_drain`) before it places
new work (`assign`). `Reconciliation` requires submitted changes to be the kept
candidates *in candidate order*, so a state that had both a completable drain
and a warm shortfall raised `ReconcileError` instead of returning a diff. Found
by a second read, not by a fixture: every drain fixture has a single host, so
no assignment candidate existed beside the drain. `reconcile()` now sorts its
candidates before bounding them, and the new test builds exactly that state.

**A test that passed for the wrong reason, twice.** The first form of
`test_changes_must_be_the_candidates_that_were_not_deferred` replaced the
submitted changes with an empty tuple. The mutation that deletes the
"changes are the kept candidates" check *survived*, because a different
invariant -- submitted plus deferred must equal candidates -- refused the
tampered value first. The test was proving a rule it was not named for. It now
swaps one kept change for the deferred one, which keeps every count equal, so
only the intended rule can refuse it. That this was found by a mutation, not by
reading the test, is the point of running them.

**A mutation harness that lied in both directions.** The first run reported
12/12 killed, but four "kills" were spurious: the hash-seed test failed on every
mutation because the throwaway tree did not contain `hub/`, which
`fleet_manager.contracts` imports. Copying `hub/` into the stand-in fixed that
and immediately exposed two real survivors (the two above). The harness then
reported only *some* kills, because fixture mutations fail as `SUBFAILED`
subtests and the driver only looked for `FAILED` lines. Both are harness
defects, recorded because a mutation table produced by a broken detector is not
evidence.

**A malformed-candidate test asserting the wrong field.** The first version made
an `assign` with no parameters at all and expected the message to name
`host_id`; validation names the first missing parameter, `assignment_id`. The
test now omits exactly one parameter so the assertion is about the check, not
about parameter order.

## Gates, re-run by me (from the workflow's list)

| Gate | Result |
| --- | --- |
| `openspec validate --all --strict` | 39 items, 0 failed |
| `specs-validate-negative-control.sh` | rc 0, refused as designed |
| `tests/gen_floors.py --check` | 125 suites, 1743 tests, floors hold |
| `check_manifest_join.py --repo .` | OK, both directions |
| `guardrails-scan.mjs` | 33 non-blocking warnings, pattern scan clean |
| `spec_traceability.py --root . --ratchet` | 110/153, ratchet raised 106 to 110 |
| `check_boundary.py --repo .` | 24 files, all declared |
| `artifact_hygiene.py --repo . --audit` | OK |
| `check_exec_bits.py` | 116 shebang'd files, all 100755 |
| `check_charset.py --repo .` | OK |
| `check_encoding.py --repo .` | OK |
| `check_corruption.py --repo .` | OK |
| `silent-success-scan.sh` | OK |
| `failure_registry_check.py` | rc 0 (two pre-existing stale-entry warnings) |
| `rules_check.py` | OK |
| `extraction_rehearsal.py --source .` | OK, both phases |
| `pytest fleet-manager/tests -q` | 133 passed, 50 subtests |
| `pytest tests -q` | 1743 passed, 182 subtests |
| `regression_check.py --base origin/main` | staged-tree run: 0 over hard limit; `fleet-manager/` is reported as a size-gate scope gap, so I measured it by hand — `reconcile.py` is 732 lines against a 300 soft limit, second only to `model.py` (663) in the package, and one concern (the diff), not several |

## What this deliberately does not do

No runtime contact and no adapter call, so nothing here starts, drains or
destroys a runner. No observation store and no staleness policy: a report is
used as given and its `observed_at` is carried into the id, but nothing refuses
a stale one -- that is a policy decision with an operator, not a default.
No `release`, `drain` or `rollout` candidate: those need proof that a runner
finished, which arrives with the host agent (Sprint 3) and the adapters
(Sprint 4); `bound_candidates()` already accepts and caps those kinds, and its
tests drive the caps with them today. No scheduling loop and no API surface
(Sprint 7): `reconcile()` is a pure function of one revision and one report per
host.
