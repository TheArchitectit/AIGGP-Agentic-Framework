# Fleet Manager one-job lifecycle (Sprint 4.2)

Change: `openspec/changes/add-fleet-manager-job-lifecycle/`
Requirements: `fleet-008-01` .. `fleet-008-05` (RUN-001, RUN-002)
Boundary: `fleet-manager/` (REPO-002)

## What this slice adds

`fleet-manager/fleet_manager/lifecycle.py`, and one new value in `adapters.py`.

4.1 described the shape of an adapter and what "warm" means; it could not say
what happens to an instance after a job starts. RUN-001 says a registered runner
accepts at most one job and is destroyed afterwards; RUN-002 says a replacement
shall not join capacity until the previous instance's cleanup is proven or its
resources are quarantined. Those two sentences are this slice, as values and
transitions.

Nothing here runs a process. `CleanupEvidence` is a value a host will report in
4.3, and this module is the rule that will judge it — the disposal results and
timestamps are validated, not observed. That is the same split 4.1 made between
the contract and an implementation of it, for the same reason: a rule that can
only be tested by running a container is a rule with no tests until a host is
available.

## The rule is about the replacement, not the destroy

Destroying an instance is an operation; admitting its replacement is a decision,
and RUN-002 constrains the decision. So the gate records instances that have
been destroyed and are neither proved clean nor quarantined, and it is
`admit_replacement(gate, pool, instance, replacing=...)` that consults it. New
capacity — a pool growing within its own contract — is not held up by somebody
else's unfinished accounting. The alternative reading (hold every admission
until the gate is empty) would make one lost instance stop a fleet, which is not
what the requirement says and not what an operator would want.

`AdmissionGate.shortfall` is the number of instances whose capacity cannot be
replaced yet, so a manager can report the size of the problem rather than only
refusing.

## Clean by proof

Five fields, one of them optional:

| field | required | why |
| --- | --- | --- |
| instance identity | yes | a proof about "an instance" is not a proof |
| image digest | yes | a proof cannot be transplanted onto a later generation |
| job identity | **no** | RUN-002 says "if known"; an uncertain disconnect may never learn it |
| volume disposal | yes | `DISPOSED`, `ABSENT`, or `FAILED` |
| network disposal | yes | same |
| start / finish | yes | an interval with no ends is not evidence |

`ABSENT` is admissible and is not a weaker `DISPOSED`: an instance that created
no volume leaves nothing behind, and saying so is the difference between a proof
and a claim. `FAILED` is *recorded* rather than refused at construction — it is
what happened, and hiding it would lose the reason the resources are not clean.
It is refused where a proof is *used*: `CleanupEvidence.admissible` is false, and
`prove()` says so. The record survives; the admission does not.

Timestamps reuse `channel._timestamp`, which requires a UTC offset and refuses a
naive value rather than assuming one. That rule already existed for host
reports, and a cleanup proof is a host report.

## Quarantine is a state with a reason

An instance that cannot be proved clean is not dropped: it takes
`DESTROYED -> QUARANTINED` and keeps `instance_id`, `failure_kind`, and
`quarantined_at`. The gate counts it as accounted for — quarantined stock is not
capacity, but it is not an open question either. A `Quarantine` whose fields are
missing is refused by name, because a quarantine nobody can inspect is a
deletion with extra steps.

## Resource limits

`ResourceLimits(memory_mib, cpus, pids)`, required on every `EphemeralInstance`
and bounded: 65536 MiB, 32 cpus, 4096 pids. Memory and pids must be whole
numbers — a process count of 1.5 is not a smaller 2, it is not a count, and
rounding it would be a guess. The fields default to `None` only so that the
refusal can name the missing one instead of raising `TypeError: missing 1
required keyword-only argument`.

`arguments()` renders them once — `--memory <n>m --cpus <n> --pids-limit <n>` —
and `command()` splices that tuple in, so the numbers that were validated are
the numbers that are run.

## Typed errors

No ninth kind. The mapping this slice uses:

| failure | kind |
| --- | --- |
| a second job offered to an instance that took one | `POLICY_DENIAL` |
| a replacement admitted while its predecessor is unaccounted for | `POLICY_DENIAL` |
| a malformed lifecycle value (instance id, image digest) | `INVALID_DESIRED_STATE` |
| a proof that is incomplete, failed, or about another instance/image | `CLEANUP_FAILURE` |
| a pool at `warm_max` | `CAPACITY_EXHAUSTION` |
| a transition the table does not have | `UNKNOWN_STATE` |
| an instance that is not warm stock | `INVALID_DESIRED_STATE` |

Two things do **not** escape: `AdapterContractError` from the checks this module
borrows (`_identifier`, `_digest`, `WarmPool.admit`) is re-raised with a kind,
and `ChannelError` from a timestamp becomes `CLEANUP_FAILURE`. A table-driven
test walks fourteen representative failures and a second walks every path where
a contract error could have leaked.

Refusals here are `AdapterError` with a kind rather than `AdapterContractError`,
which is a deliberate departure from `adapters.py`'s convention: fleet-008-05
requires a lifecycle refusal to name its kind, and a contract error has none.

## The one place a state changes

`offer()` originally built its result with `replace(...)` directly. The first
battery caught it: deleting `PREPULLED -> ASSIGNED` from the table changed
nothing, because `offer` never consulted the table. Every transition now goes
through `_transition()`, and the table is the authority for all of them.
`finish()` and `prove()` had the mirror-image problem: each carried a check that
the table already made, and deleting either check broke no test. Both are gone;
the docstrings say where the rule lives (M8, M22).

## Mutation battery

Driver `/tmp/mutate_4_2.py`: a throwaway copy of `hub/`, `templates/` and
`fleet-manager/`, one exact textual mutation at a time, the fleet-manager suite
alone, kill = non-zero exit naming `FAILED`/`SUBFAILED`. Baseline green before
the first mutation.

**43/43 killed.**

| # | mutation | killed by |
| --- | --- | --- |
| M1 | prepulled cannot accept a job | `test_a_finished_instance_cannot_take_another_job` |
| M2 | a destroyed instance can be quarantined but not proven | `test_the_two_final_states_have_no_way_out` |
| M3 | a running job can only complete | `test_a_finished_instance_cannot_take_another_job` |
| M4 | a terminal state can walk back to warm | `test_there_is_no_transition_back_to_warm` |
| M5 | an uncertain disconnect is not terminal | `test_the_terminal_states_are_the_four_the_spec_names` |
| M6 | a second job is accepted | `test_a_finished_instance_cannot_take_another_job` |
| M7 | a job identity is not checked | `test_a_job_identity_that_is_not_an_identifier_is_refused` |
| M8 | a running job may finish into any state | `test_finish_refuses_an_outcome_that_is_not_terminal` |
| M9 | an instance may hold a job without naming it | `test_a_lifecycle_in_a_job_state_must_name_its_job` |
| M10 | a prepulled instance may name a job | `test_a_prepulled_lifecycle_cannot_name_a_job` |
| M11 | an assigned state is not a job-naming state | `test_a_lifecycle_in_a_job_state_must_name_its_job` |
| M12 | the refusal does not name the state pair | `test_there_is_no_transition_back_to_warm` |
| M13 | `next_states` takes anything | `test_next_states_refuses_something_that_is_not_a_job_state` |
| M14 | a failed disposal is still proof | `test_a_failed_disposal_is_recorded_but_is_not_admissible` |
| M15 | every disposal is proof | `test_a_failed_disposal_is_recorded_but_is_not_admissible` |
| M16 | the image digest may be missing | `test_every_field_but_job_identity_is_required` |
| M17 | an interval may run backwards | `test_the_two_final_states_have_no_way_out` |
| M18 | a bad timestamp escapes as a channel error | `test_a_timestamp_must_carry_an_offset` |
| M19 | the document always carries a job identity | `test_a_proof_without_a_job_identity_is_still_a_proof` |
| M20 | a proof is not checked against its instance | `test_a_proof_for_another_instance_cannot_be_transplanted` |
| M21 | a proof is not checked against its image | `test_a_proof_for_another_image_cannot_be_transplanted` |
| M22 | a running instance can be proved clean | `test_finish_refuses_an_outcome_that_is_not_terminal` |
| M23 | an inadmissible proof is not refused when used | `test_an_inadmissible_proof_leaves_the_instance_unproven` |
| M24 | a quarantine may name another instance | `test_a_quarantine_for_another_instance_is_refused` |
| M25 | the quarantine reason may be missing | `test_every_quarantine_field_is_required` |
| M26 | the quarantine reason is unbounded | `test_a_quarantine_reason_is_bounded` |
| M27 | the shortfall is never reported | `test_a_destroyed_instance_shortens_the_pool_until_it_is_accounted_for` |
| M28 | a destruction is recorded twice | `test_the_gate_refuses_to_record_a_destruction_twice` |
| M29 | the gate proves what it is not awaiting | `test_the_gate_proves_only_what_it_is_awaiting` |
| M30 | the gate quarantines what it is not awaiting | `test_the_gate_quarantines_only_what_it_is_awaiting` |
| M31 | a replacement is admitted before its predecessor is accounted for | `test_a_replacement_is_not_admitted_while_the_predecessor_is_unaccounted` |
| M32 | the ceiling is not checked when admitting | `test_a_pool_at_its_ceiling_is_capacity_exhaustion` |
| M33 | a pool exactly at its ceiling still admits | `test_a_pool_at_its_ceiling_is_capacity_exhaustion` |
| M34 | an unusable instance is admitted | `test_admitting_something_that_is_not_warm_stock_is_a_desired_state_error` |
| M35 | a missing limit is accepted | `test_every_limit_is_required_and_named_when_missing` |
| M36 | a non-positive limit is accepted | `test_a_non_positive_limit_is_refused` |
| M37 | an unbounded limit is accepted | `test_a_limit_above_its_bound_is_refused` |
| M38 | a fractional count is accepted | `test_a_limit_that_is_not_a_number_is_refused` |
| M39 | a boolean is a number | `test_a_limit_that_is_not_a_number_is_refused` |
| M40 | memory is rendered without its unit | `test_the_command_carries_the_limits_it_was_built_with` |
| M41 | the cpu limit is rendered with a trailing zero | `test_the_limits_are_rendered_as_the_runtime_spells_them` |
| M42 | a job instance may be built without limits | `test_a_job_instance_cannot_be_built_without_resource_limits` |
| M43 | the command omits the limits | `test_the_command_carries_the_limits_it_was_built_with` |

The `killed by` column names the test that failed first, which is not always the
test that was written for the rule: M17 makes the evidence builder itself fail,
so the first test to construct a proof reports it. The mutation was still killed
by a named test, which is what the battery exists to show.

### Three survivors in the first run, and none of them was a missing test

The first run was 43 mutations, 40 killed, **3 survived**, and all three were
real findings rather than gaps in the suite:

- **M1** — `offer()` bypassed the transition table. Deleting
  `PREPULLED -> ASSIGNED` changed nothing because `offer` never consulted it.
  Fixed in the code: every transition goes through `_transition()`.
- **M8** — `finish()` re-checked that its outcome was a terminal state. The
  only state `finish` can act from is `RUNNING`, whose arrows *are* the four
  terminal states, so the check was unreachable. Deleted; the docstring says
  where the rule lives.
- **M22** — `prove()` re-checked that the instance was `DESTROYED`. `move()`
  already refuses `PROVEN_CLEAN` from anywhere else. Deleted, and
  `quarantine()`'s copy with it.

That is the fourth dead duplicate guard found by a battery in four slices
(3.2's M18, 4.1's M25, and these two), and the same conclusion each time: a
guard that no mutation can kill and no test needs is a second statement of a
rule, and the second statement is the one that drifts.

## Gates

Run by hand from the repository root after staging (the hygiene and size gates
do not see untracked files):

| gate | result |
| --- | --- |
| `pytest tests/ -q` | 1747 passed, 182 subtests |
| `pytest fleet-manager/tests -q` | 422 passed, 382 subtests |
| `fleet-manager/scripts/extraction_rehearsal.py --source .` | OK — boundary stands alone, core stands without it |
| `node tests/test_guardrails_scan.mjs` | ALL TESTS PASSED |
| `pytest tests/test_python_root_anchor.py` | 7 passed |
| `node tests/test_scanner_root_anchor.mjs` | all root-anchor checks passed |
| `node scripts/run-tests.mjs` | 2173 passed, 0 failed across 139 files |
| `node scripts/guardrails-scan.mjs` | pattern scan clean, 33 warnings (non-blocking) |
| `node scripts/semantic-scan.mjs` | clean (SEMANTIC-001, SEMANTIC-005) |
| `bash scripts/silent-success-scan.sh` | OK — 1727 allowlist entries |
| `scripts/failure_registry_check.py` | rc 0 (stale-path warnings) |
| `scripts/rules_check.py` | OK |
| `scripts/check_exec_bits.py` | 116 shebang'd files, all 100755 |
| `scripts/check_charset.py --repo .` | OK — 841 text files |
| `scripts/check_encoding.py --repo .` | OK — 841 text files |
| `scripts/check_corruption.py --repo .` | OK — 841 text files |
| `tests/gen_floors.py` | OK — 125 suites, 1747 tests |
| `scripts/check_manifest_join.py --repo .` | OK — 1 join |
| `scripts/artifact_hygiene.py --repo . --audit` | OK — every upload step bound |
| `scripts/check_boundary.py --repo .` | OK — 37 files under `fleet-manager/` |
| `openspec validate --all --strict` | 44 passed, 0 failed |
| `scripts/specs-validate-negative-control.sh` | passed — the validator refused a malformed fixture |
| `scripts/spec_traceability.py --root . --ratchet` | 133/176 covered; ratchet raised 128 -> 133 |
| `scripts/regression_check.py --base origin/main --pre-commit` | 0 over hard limit, 38 soft (warning), 4 scope gaps |
| `scripts/secret-scan.sh --range <before>..HEAD` | see below |

The boundary gate found `fleet-manager/.pytest_cache/` — left behind by a
suite run started from inside the package directory — and refused it as five
undeclared paths. The cache is pytest's own, untracked, and regenerable; it was
removed (not with `git clean`), and the gate then reported 37 declared files.

## Deliberately absent

- **No adapter implementation and no process.** `Disposal.DISPOSED` is a value
  this module believes; producing it from a host, with a volume that is really
  gone, is 4.3.
- **No change to the error taxonomy.** Eight kinds in, eight kinds out.
- **No host-side evidence collection.** The start and finish timestamps come
  from whoever reports them; checking them against a host clock is 4.3's.
- **No Docker evidence.** The fleet runs rootless Podman; the command renders
  whichever runtime the pool declares, and nothing here has been run against
  Docker.
- **No change to the warm-pool contract.** 4.1's `WarmPool` still refuses used
  stock; this slice adds the accounting for the instance that has left it.
