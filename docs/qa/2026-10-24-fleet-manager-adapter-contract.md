# QA: Fleet Manager adapter contract (Sprint 4.1, FLEET-007)

Date: 2026-10-24
Change: `openspec/changes/add-fleet-manager-adapter-contract`
Box: `devgate-product-tiers-fleet-manager` 4.1 — stable adapter contract;
pinned ephemeral runner image; warm-pool behavior.

## What this slice adds

- `fleet-manager/fleet_manager/adapters.py` (535 lines) — the eleven-call
  contract, the structural checker, the eight typed errors, the image pin, the
  warm pool, and the ephemeral instance.
- `fleet-manager/tests/test_adapters_v1.py` (666 lines) — 55 tests,
  floor-pinned to this module.

No process is started, no container is created and no image is built, which is
the point of the box: 4.2 implements the contract, and a contract that has
never been separated from its first implementation is just that
implementation's habits.

## The contract is checked without being called

`ADAPTER_CALLS` is the program's Sec. 5.2 list in the program's order.
`check_contract()` uses `inspect.signature` and reports every problem in one
refusal. Three parameter names carry a rule rather than data:

| call | parameter | why it is in the contract |
| --- | --- | --- |
| `ensure_image` | `digest` | an immutable artifact, never a tag |
| `create_runner` | `registration_ref` | a reference; a parameter named `registration_token` or `secret` is refused by name |
| `cancel_or_timeout` | `policy` | cancellation only under an explicit policy |
| every mutating call | `operation_key` | idempotent or durably keyed (Sec. 5.2) |

The suite proves the checker never calls the adapter by building a fake whose
signatures are correct and whose bodies all raise: it still conforms. That is
the difference between this check and a conformance test that calls eleven happy
paths — the latter proves today's behaviour, this one states the promise.

A `**kwargs` does not satisfy a required name: a catch-all accepts a call it
does not implement, so it is the shape a smuggled operation hid in last sprint.

Runtime is declared on the adapter as a value (`runtime = Runtime.PODMAN`) and
compared with the pool's. An adapter that declares `"podman"` as a string is
refused too: a string that spells a runtime is a string.

## Errors are typed, and the detail is withheld

`ErrorKind` holds exactly the eight Sec. 5.2 kinds; a string that spells one is
refused at construction. `AdapterError.detail` is refused **without being
echoed** when it matches the credential shape `audit` already defines, and
`classify()` turns an unexpected exception into `RUNTIME_FAILURE` naming the
exception's **type only** — an arbitrary message is where a failed
`podman login` puts what it was given.

## The image pin has one source

`STANDARD_RUNNER_IMAGE_DIGEST` is the digest recorded in
`templates/runner/self-hosted-runner.container`, and a skip-guarded test parses
that quadlet's `Image=` line and fails if the two differ (skip-guarded because
the extraction rehearsal copies only `fleet-manager/`). `image_reference()`
refuses a tag, a full reference, and anything that is not `sha256:<64 lowercase
hex>`; the three refusals are distinct because the three mistakes are.

**On "build a pinned ephemeral runner image": this slice does not build one,
deliberately.** The repository's runner standard says, in its own words, "Do NOT
hand-roll a runner image" and "Do NOT fork the entrypoint — all runners on a host
share one bind-mounted `dg-entrypoint.sh`". The pinned image the program asks
for is the stock official `ghcr.io/actions/actions-runner`, and what 4.1 adds is
the *ephemeral instance contract* that makes the stock image safe to use
ephemerally. Building a fork would contradict the standard this repository
already ships; if the box is later read as requiring a fleet-owned image, that
is a decision for the owner, not a default.

## Warm is a state, not a count

`WARM_STATES` is exactly `PREPULLED` and `STOPPED_CLEAN`. `USED` and
`QUARANTINED` are states, not absences — an instance that has run a job still
exists and still holds its name, which is exactly why it must not be counted.
`WarmPool` binds every instance to the pool's id **and** pinned digest (so last
generation's container cannot be counted against this one), refuses duplicates,
refuses stock above `warm_max`, and reports the shortfall below `warm_min`.

## The ephemeral command is defined by what it lacks

```
podman run --rm --name job-1 --label devgate.pool=phase1-linux \
  --env EPHEMERAL=true --env-file /run/devgate/phase1-linux.secrets.env \
  ghcr.io/actions/actions-runner@sha256:e549...
```

No `-v`, no `--mount`, no `/_work`: the persistent standard's durable work
volume is exactly the thing RUN-001 forbids a job container to have. The
registration reference reaches the runner through `--env-file`, never as
`-e RUNNER_TOKEN=<value>` — a value in argv is visible in `ps` and in shell
history, which is the leak `templates/runner/add-a-runner.md` is careful about.

## Mutation battery

Driver `/tmp/mutate_4_1.py`: a throwaway copy of `fleet-manager/` and `hub/`,
one exact textual mutation at a time, the adapters suite alone, kill = non-zero
exit naming `FAILED`/`SUBFAILED`. Baseline green before the first mutation.

**33/33 killed.**

| # | mutation | killed by |
| --- | --- | --- |
| M1 | the contract drops a call | `test_the_contract_is_the_eleven_calls_the_program_names` |
| M2 | a mutating call stops being mutating | `test_the_mutating_calls_are_the_six_that_change_a_host` |
| M3 | `ensure_image` no longer needs a digest | `test_a_catch_all_signature_does_not_satisfy_a_required_name` |
| M4 | `create_runner` asks for the material | `test_a_complete_adapter_conforms` |
| M5 | material-shaped parameters are accepted | `test_create_runner_asks_for_a_reference_not_the_material` |
| M6 | a catch-all satisfies a required name | `test_a_catch_all_signature_does_not_satisfy_a_required_name` |
| M7 | the runtime mismatch is accepted | `test_the_wrong_runtime_is_refused` |
| M8 | the declared runtime may be any value | `test_an_adapter_that_declares_no_runtime_is_refused` |
| M9 | missing calls are skipped silently | `test_a_missing_call_is_named` |
| M10 | only the first missing call is reported | `test_every_missing_call_is_reported_at_once` |
| M11 | any kind is accepted | `test_an_unknown_kind_is_refused` |
| M12 | a credential-shaped detail is accepted | `test_a_detail_that_looks_like_a_credential_is_withheld` |
| M13 | an unbounded detail is accepted | `test_a_long_detail_is_refused` |
| M14 | `classify` records the exception message | `test_an_unexpected_exception_is_classified_by_type_only` |
| M15 | `classify` stops passing an `AdapterError` through | `test_classify_passes_an_adapter_error_through` |
| M16 | a tag pins an image | `test_a_digest_must_be_lowercase_hex_of_the_right_length` |
| M17 | a full reference is a digest | `test_a_reference_is_not_a_digest` |
| M18 | uppercase hex is a digest | `test_a_digest_must_be_lowercase_hex_of_the_right_length` |
| M19 | a running container is warm | `test_only_two_states_are_warm` |
| M20 | used stock is warm stock | `test_a_warm_pool_refuses_used_stock` |
| M21 | warm stock from another image is counted | `test_warm_stock_from_another_image_is_refused` |
| M22 | warm stock from another pool is counted | `test_warm_stock_from_another_pool_is_refused` |
| M23 | duplicate ids are accepted | `test_duplicate_instance_ids_are_refused` |
| M24 | stock above the ceiling is accepted | `test_warm_stock_above_the_ceiling_is_refused` |
| M25 | admitting at the ceiling is allowed | **survived — see below** |
| M26 | the shortfall is never reported | `test_shortfall_and_floor` |
| M27 | retiring an unknown instance is silent | `test_retiring_an_unknown_instance_is_refused` |
| M28 | a job instance may keep a work directory | `test_a_job_instance_has_no_work_directory` |
| M29 | a job instance may outlive its job | `test_a_job_instance_is_removed_on_exit` |
| M30 | the command mounts a durable volume | `test_the_command_mounts_no_durable_volume` |
| M31 | the command names the registration material | `test_the_command_never_names_the_registration_material` |
| M32 | the container is not removed on exit | `test_the_command_is_ephemeral_and_named` |
| M33 | the command runs a tag, not the digest | `test_the_command_runs_the_pinned_image` |
| M34 | an environment assignment is a path | `test_an_env_file_that_is_an_assignment_is_refused` |

### M25 survived, and the mutation was right

The battery is numbered to 34 because M25's guard was **deleted** after it
survived. `WarmPool.admit()` carried its own `warm_count >= warm_max` check, and
planting `if False:` there broke nothing: `WarmPool.__post_init__` already
refuses the same construction, and its message already names capacity
exhaustion. The guard was a second statement of one rule — the same finding as
3.2's M18, and the same resolution: delete the unreachable copy, say in
`admit()`'s docstring where the rule lives, and keep the test that proves the
ceiling holds. The final battery is 33 mutations, 33 killed.

## Gates

Run by hand from the repository root after staging (the hygiene and size
scanners do not see untracked files).

| gate | result |
| --- | --- |
| `openspec validate --all --strict` | 43 passed, 0 failed |
| `scripts/specs-validate-negative-control.sh` | passed — strict validation refused the malformed fixture naming its defect, exit 1 |
| `tests/gen_floors.py --check` | 125 suites, 1743 tests — floors hold (core only) |
| `scripts/spec_traceability.py --root . --ratchet` | 128/171 covered; ratchet raised 124 → 128 |
| `scripts/check_boundary.py --repo .` | 35 files under `fleet-manager/`, all declared |
| `scripts/check_exec_bits.py` | 116 shebang'd files, all 100755 |
| `scripts/check_manifest_join.py --repo .` | OK — 1 join agrees both directions |
| `scripts/check_charset.py --repo .` | OK — 834 text files within baseline (this document included) |
| `scripts/check_encoding.py --repo .` | OK — 834 text files within baseline |
| `scripts/check_corruption.py --repo .` | OK — 834 text files within baseline |
| `node scripts/guardrails-scan.mjs` | pattern scan clean (33 non-blocking warnings) |
| `node scripts/semantic-scan.mjs` | clean (SEMANTIC-001, SEMANTIC-005) after installing `typescript@5` |
| `scripts/silent-success-scan.sh` | OK — every detected marker allowlisted or excluded |
| `scripts/failure_registry_check.py` | exit 0 (two stale-path warnings, both in unrelated trees) |
| `scripts/rules_check.py` | OK — every enabled rule has a registered checker |
| `scripts/artifact_hygiene.py --repo . --audit` | OK — every upload step bound |
| `fleet-manager/scripts/extraction_rehearsal.py --source .` | OK — boundary stands alone, core stands without it |
| `pytest fleet-manager/tests -q` | 351 passed, 218 subtests |
| `pytest tests -q` | 1743 passed, 182 subtests |
| `regression_check.py --base 1b4cbd2 --fail-if-empty --pre-commit` | 0 over hard limit, 0 pre-existing oversize, 37 over soft limit, 4 scope gaps |

Two notes:

- The semantic scan first exited 0 while evaluating **nothing** — "the gate
  evaluated NOTHING — this is a tooling error, not a clean scan". Installing the
  pinned compiler produced the real result above. A gate that runs nothing and
  exits 0 is the failure mode this repository usually catches; here it printed a
  clear warning, which is why it was caught.
- `regression_check.py` still reports `fleet-manager/` as outside the size-gate
  scope, so the line counts in this document are `wc -l`, not a gate result.

## Deliberately absent

- **No adapter implementation.** 4.2 implements this contract. Until then
  conformance is proven against fakes, and a fake cannot start a container.
- **No execution.** The module builds an argument list as a value; nothing in
  the package starts a process.
- **No image build**, for the reason above: the repository's runner standard
  rejects hand-rolled runner images and forked entrypoints.
- **No lifecycle, cleanup proof, or quarantine.** RUN-002's "no replacement
  joins capacity until cleanup is proven or resources are quarantined" is the
  next box; `InstanceState.QUARANTINED` exists here so 4.2 does not have to add
  a state to a closed enum.
- **No Docker evidence.** The fleet runs rootless Podman; the Docker path is
  identical by construction (the binary name is the only difference in the
  rendered command) and has not been exercised on a host, which 4.3 states as a
  residual rather than claiming here.
