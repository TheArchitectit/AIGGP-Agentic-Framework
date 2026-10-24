# Fleet Manager desired-state models — evidence

Date: 2026-10-24 (UTC). Program package `devgate-product-tiers-fleet-manager`,
Sprint 2 box 2.1 (repository, host, pool, assignment, capacity, drain and
rollout models — FLEET-001). Openspec change:
`add-fleet-manager-domain-models` (`fleet-001-01..05`).

## What landed

- `fleet_manager/model.py` — frozen `Repository`, `Pool`, `Host`, `Assignment`,
  `Capacity`, `Drain`, `Rollout`; `DesiredState`, whose every transition
  returns a new revision.
- `fleet_manager/observation.py` — `Observation` / `ObservedRunner`: what a
  host reports.
- `fleet_manager/documents.py` — the store's closed wire form:
  `to_document()` / `from_document()`, missing field named, unknown field
  refused, secret-shaped keys refused.
- `tests/test_model_v1.py` — 36 tests, floor-pinned; `pytest fleet-manager/tests`
  is now **60 passed**.

## What the model refuses, and why each one matters

| refusal | why it is a refusal and not a default |
| --- | --- |
| pool missing a required field (named) | the alternative is a pool that works by accident, with the missing thing filled in by whoever reads it last |
| unknown document field | a store that drops what it does not understand will one day drop `secret_profile` and keep serving |
| `ephemeral: false` | the v1 capacity contract declares `demand.ephemeral` as `const true`; a persistent pool is a fleet the contract cannot request |
| `warm_min > warm_max > scale_ceiling` | three numbers that disagree are three bugs waiting for a load spike |
| both `allowed_repositories` and `runner_group` (or neither) | "who may run here" must have exactly one answer |
| unpinned image (`:latest`, a tag) | a tag is not a pin; a rollout to a tag records a change nobody can reproduce |
| rollback image equal to the current image | a "rollback" to the same image is a no-op recorded as safety |
| `registration_token` / `password` / `secret` / `private_key` keys | secrets are referenced by profile; the refusal does not repeat the value |
| `secret_profile` holding a blob rather than an identifier | same rule, caught at the one field allowed to mention secrets |
| assignment to a host that lacks the runtime, the architecture, the pool on its allow-list, or is not active | the four ways "it should work" stops being true |
| assignment beyond the host's slots | capacity is computed here or it is computed differently in three places |
| completing a drain with work still assigned | the drain would report done while jobs are still running |
| roll out to the image already running | it would record a change that is not one |

## The separation is structural, not a comment

`model.py` and `observation.py` do not import each other, and a test parses both
files with `ast` and fails if either gains an import of the other. `DesiredState`
also type-checks its collections before anything else, because an `Observation`
carries a `host_id` — "it has the field" is exactly the argument a host agent
would win with. `DesiredState(hosts=(observation,))` is refused naming the type.

## Planted mutations

Each mutation was applied to a throwaway copy of the package and the suite run
against it. Every one killed at least one test written for it:

| mutation | tests that failed |
| --- | --- |
| capacity saturation check removed | `test_over_capacity_is_refused_and_names_free_slots` |
| host type check in `DesiredState` removed | `test_an_observation_cannot_be_desired_state` |
| secret-shaped-key guard removed | `test_a_value_shaped_key_is_refused_by_name_without_echoing`, `test_a_nested_secret_key_is_refused_by_path` |
| identical-rollout check removed | `test_a_rollout_to_the_current_image_is_refused` |
| `ephemeral` Phase-1 const removed | `test_a_persistent_pool_is_refused_in_phase_1` |
| allow-list check removed | `test_a_pool_off_the_allow_list_is_named` |
| drain-completion outstanding-work check removed | `test_completing_a_drain_with_work_in_flight_is_refused` |
| closed-document check removed | `test_an_unknown_field_is_refused`, `test_an_unknown_top_level_field_is_refused` |

Every run also reported one unrelated failure,
`test_the_declared_build_inputs_are_the_pinned_import_surface`, which asserts
that the rehearsal's declared build inputs exist at the repository root — true
in the checkout, false in a bare copy of the package. It is a copy artifact, not
a mutation effect, and it is named here so the mutation table is not read as
eight clean runs.

## Gate runs (all re-run in this window)

| gate | result |
| --- | --- |
| `npx --no-install openspec validate --all --strict` | **37/37 items** |
| `bash scripts/specs-validate-negative-control.sh` | exit 0 |
| `python3 tests/gen_floors.py --check` | OK — 125 suites, 1743 tests (open-core tree unchanged) |
| `python3 scripts/check_manifest_join.py --repo .` | OK |
| `node scripts/guardrails-scan.mjs` | pattern scan clean |
| `python3 scripts/spec_traceability.py --root . --ratchet` | **102/145**, ratchet raised 97 → 102 |
| `python3 scripts/regression_check.py --base origin/main --pre-commit` | rc 0, 0 over hard limit |
| `python3 scripts/artifact_hygiene.py --repo . --audit` | audit OK |
| `python3 scripts/check_boundary.py --repo .` | OK — 16 files, all declared |
| `python3 scripts/check_exec_bits.py` | OK — 116 shebang'd files, all 100755 |
| `python3 -m pytest fleet-manager/tests -q` | **60 passed** (24 contracts + 36 model) |
| `python3 fleet-manager/scripts/extraction_rehearsal.py --source .` | OK — both phases, package still stands alone |

## Two leniencies a second read found (fixed in `7f0fa4a`)

Neither was caught by a test, which is why both are recorded:

- `documents._pairs()` coerced label names and values with `str()`, so
  `{"pool": 5}` became `{"pool": "5"}` and then passed the string check
  downstream. A closed document that re-types its values is not closed.
- `Assignment` compared `issued_at` and `released_at` as strings, which is only
  correct while every timestamp carries the same offset. It parses them now.

Both are pinned by tests; the suite went 34 → 36.

## What this deliberately does not do

- **No plan, no apply, no idempotency keys.** 2.2. A transition here is one
  operation on one aggregate; a bounded plan with capacity impact needs it.
- **No reconciler and no diff.** `Observation` exists to be compared with
  desired state by 2.3, which computes the diff. A comparison returns a diff,
  never a state.
- **No persistence.** The document is the shape the store will keep; the store
  is not in this change.
- **No runtime contact.** `Runtime` names docker and podman; nothing here opens
  a socket, reads a file, or shells out.
- **No host-state observation.** `Observation` reports runners only. Host
  health, disk and adapter capability reports belong to the host-agent contract
  (Sprint 3) and will be added there rather than guessed here.

## Stated limits

- **A wide model.** A pool carries 25 document fields because the program's
  §4.3 requires them. Collapsing them into an "extras" map would move the
  validation into the store and lose the field-named refusals.
- **Rollback is one image.** A two-step rollback reads the rollout ledger, not
  a field. Stated so nobody assumes a stack.
- **Reference-shaped is not authenticated.** `secret_profile: "phase1-job-secrets"`
  proves the document does not carry a secret; it cannot prove the profile
  exists. Resolving profiles is the secret subsystem's job (Sprint 5).
