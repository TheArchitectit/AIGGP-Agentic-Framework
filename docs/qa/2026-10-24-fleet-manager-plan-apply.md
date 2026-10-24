# Fleet Manager plan and apply — evidence

Date: 2026-10-24 (UTC). Program package `devgate-product-tiers-fleet-manager`,
Sprint 2 box 2.2 (plan/apply with revisions and idempotency — FLEET-002; audit
events; API authn/authz skeleton). Openspec change:
`add-fleet-manager-plan-apply` (`fleet-002-01..04`).

## What landed

- `fleet_manager/plan.py` — `Change`, `CapacityImpact`, `Plan` (identity is a
  digest of base revision + ordered changes, recomputed on construction),
  `build_plan()`, `plan_clock()`, `simulate()`.
- `fleet_manager/apply.py` — `apply_plan()`, `IdempotencyLedger`,
  `ApplyRefused` (a refusal carries the log entry recording it).
- `fleet_manager/audit.py` — `AuditLog` / `AuditEvent` / `Outcome`.
- `fleet_manager/auth.py` — `Principal`, `PrincipalKind`, `Scope`, the ladder
  read < plan < apply < admin.
- `tests/test_plan_apply_v1.py` — 44 tests; `pytest fleet-manager/tests` is
  now **104 passed**.

FLEET-002's plan elements are covered by change kinds: creates (`assign`),
drains (`drain`, `complete_drain`), replacements (`rollout`), deletions
(`release`), capacity impact (computed per host from the simulation).

## What it refuses, and why each one matters

| refusal | where | why it is a refusal |
| --- | --- | --- |
| a plan whose id does not match its changes | `Plan` construction | otherwise "reviewed plan A" does not constrain "applied plan A" |
| an empty plan | `build_plan` | an apply with no work is a receipt for nothing |
| an impossible change, named by index | `build_plan` | the failure has to arrive while it is still cheap |
| a stale plan (base ≠ current revision) | `apply_plan` | rebasing onto newer state is a plan nobody reviewed |
| apply without `fleet.apply` | `apply_plan` | read-only principals do not mutate |
| a destructive plan without `fleet.admin` | `apply_plan` | releasing, draining and rolling out end running work |
| a key re-used for a different plan | `apply_plan` | widening a key is how a retry becomes a second deploy |
| a ledger entry for a key that exists | `IdempotencyLedger` | the ledger is appended to, never rewritten |
| a bad key shape / bad `at` | `apply_plan` | refused before any work, not after |
| a log with a gap, a reorder or a duplicate seq | `AuditLog` | a hole in a log is indistinguishable from a deletion |
| an entry earlier than its predecessor | `AuditLog` | a log you can back-date is not evidence |
| a reason that matches a credential shape | `AuditEvent` | the refusal must not become the place the value is stored |
| a scope string instead of a `Scope` | `Principal` | `"fleet.admin"` is not a decision |
| an apply that produces a revision the plan did not declare | `apply_plan` | an implementation fault, returned as an error, never as success |

## Three defects found while building this slice

None of these were caught by review of the finished code; each was caught by a
test written before the code worked, and each is pinned now.

1. **A fixed sentinel clock made planning a release impossible.** Simulating at
   the epoch refused `release` against any state created after 1970, because an
   `Assignment` refuses a release before its issue. A plan must not read the
   wall clock, but it also must not precede the work it acts on — so the clock
   is derived from the state (`plan_clock`: the newest timestamp the state
   carries), which is deterministic per revision. Caught by
   `test_a_plan_that_frees_a_slot_reports_it`.
2. **Audit entries were committed as they were produced.** When a later change
   failed, the log still said `applied` for the earlier one — work that was
   discarded with the working copy. Entries are now buffered and committed only
   if the whole plan applied, because a plan is one revision and its record
   must appear as one. Caught by
   `test_a_failure_mid_plan_is_a_refusal_and_the_log_says_so`.
3. **The suite floor counted its neighbours.** `discover()` over the test
   directory made the floor pass on any file's tests, so a file could shrink
   unnoticed — the 2.1 floor was already vacuous. Both suites now count their
   own module (`loadTestsFromModule`). Caught while adding the 2.2 floor.

A fourth, smaller one: `_host_of` returned `None` for `release`, so a release
plan reported no capacity impact at all; the impact tests caught it.

## Planted mutations

Each was applied to a throwaway copy of the package and the suite run against
it (`/tmp/mutate_2_2.py`). **10/10 killed:**

| mutation | tests that failed |
| --- | --- |
| plan clock ignores the state (the original sentinel bug) | `test_a_plan_that_frees_a_slot_reports_it`, `test_a_destructive_plan_requires_admin`, `test_a_plan_is_destructive_when_any_change_is`, `test_an_admin_may_apply_a_destructive_plan` |
| plan id not recomputed | `test_a_plan_whose_id_no_longer_matches_its_changes_is_refused` |
| stale-revision check removed | `test_a_stale_plan_is_refused_naming_both_revisions`, `test_a_second_key_for_the_same_plan_is_a_stale_apply` |
| destructive apply no longer requires admin | `test_a_destructive_plan_requires_admin` |
| audit entries committed as they go | `test_a_failure_mid_plan_is_a_refusal_and_the_log_says_so` |
| contiguous-sequence check removed | `test_a_gap_in_the_sequence_is_refused` |
| backwards-clock check removed | `test_a_log_that_runs_backwards_is_refused` |
| a key may be widened to a different plan | `test_a_key_cannot_be_reused_for_a_different_plan` |
| capacity impact not reported | `test_the_capacity_impact_is_computed_from_the_simulation`, `test_a_plan_that_frees_a_slot_reports_it`, `test_the_plan_document_carries_the_changes_in_order_and_the_impact` |
| credential-shaped reason stored | `test_a_reason_that_looks_like_a_credential_is_refused_without_echoing` |

Unlike the 2.1 table, these runs are clean: 2.2's mutations only touch
`plan.py`, `apply.py` and `audit.py`, so the copy-artifact failure that the
rehearsal test produces in a bare package copy does not appear when only
`test_plan_apply_v1.py` runs.

## Gate runs (all re-run in this window)

| gate | result |
| --- | --- |
| `npx --no-install openspec validate --all --strict` | **38/38 items** |
| `bash scripts/specs-validate-negative-control.sh` | exit 0 |
| `python3 tests/gen_floors.py --check` | OK — 125 suites, 1743 tests |
| `python3 scripts/check_manifest_join.py --repo .` | OK |
| `node scripts/guardrails-scan.mjs` | pattern scan clean (33 non-blocking warnings) |
| `python3 scripts/spec_traceability.py --root . --ratchet` | **106/149**, ratchet raised 102 → 106 |
| `python3 scripts/artifact_hygiene.py --repo . --audit` | audit OK |
| `python3 scripts/check_boundary.py --repo .` | OK — 21 files, all declared |
| `python3 scripts/check_exec_bits.py` | OK — 116 shebang'd files, all 100755 |
| `python3 -m pytest fleet-manager/tests -q` | **104 passed** (24 contracts + 36 model + 44 plan/apply) |
| `python3 fleet-manager/scripts/extraction_rehearsal.py --source .` | OK — both phases |
| `python3 -m pytest tests -q` | **1743 passed**, 182 subtests |

## What this deliberately does not do

- **No HTTP, no token verification, no sessions.** `Principal` is what
  authentication *produces*; the API layer that produces it is Sprint 7.
- **No persistence.** The ledger and the log are frozen values the caller keeps.
  Where they are stored, and how the store compares-and-sets, is not here.
- **No reconciliation.** A plan is built from desired state alone. Comparing it
  with an `Observation` is 2.3, and that comparison yields a diff, not a plan.
- **No concurrency control.** Two applies against the same revision with
  different keys both succeed if they are serialized; the revision check
  catches the non-serialized case only when the state has already moved.
- **No rollback of a plan.** A plan is all-or-nothing because it produces one
  revision; undoing an applied revision is a new plan, not an inverse.

## Stated limits

- **`plan_clock` is derived, not observed.** It is the newest timestamp the
  state carries, which is deterministic and never precedes the work, but it is
  not the time the change will happen. Apply stamps the real time; a plan's
  simulated timestamps are placeholders by construction.
- **The audit log is only as append-only as its storage.** The type refuses
  edits, gaps and back-dating; a store that does not preserve the value can
  still lose it. The log's integrity proof is a Sprint 3/4 concern.
- **Authorization is a ladder with no resource scoping.** Every `fleet.apply`
  principal may apply to every pool. Per-pool or per-repository scoping is not
  modelled, and modelling it badly would be worse than naming the gap.
- **`ApplyRefused` is an exception that carries a value.** Callers must persist
  `.audit_log`; a caller that only formats `str(exc)` loses the entry. The API
  layer's tests will need to pin that (Sprint 7).
