# gameSessionStart, step 1 - exit evidence

Date: 2026-10-25 (UTC). Change package:
`openspec/changes/add-game-session-start/` (this repo). Design:
`docs/superpowers/specs/2026-09-29-game-session-start-design.md` (approved for
implementation planning, 2026-09-29, rollout step 1 of 5).

Tracker: `spec-audit-rollout` box 4.2 - the work-session advisory's
`worst-tracked gaps: N` line, fed by the gap scanner's JSON so the scanner has
one consumer and the session block has one inventory source.

## What landed

Commit `e2a677c`:

| File | Role |
|---|---|
| `scripts/game_session_start.py` | the brain: validate, rule, advise, log |
| `.guardrails/prevention-rules/session-manifest.schema.json` | `aiggp.session/v1`, with both conditionals named in its description |
| `tests/test_game_session_start.py` | 37 tests |
| `tests/expected-counts.json` | floor row `test_game_session_start: 33` (the manifest-join gate requires one) |
| `scripts/game-framework-README.md` | `determinism.enabled` contract, absent = off |
| `CHANGELOG.md` | Unreleased / Added |

Six requirements (`session-01`..`session-06`) in the delta spec, all covered by
source markers. The published-spec count moved 44 -> 45 items under
`validate --all --strict`; no requirement body exceeds 500 characters (194
requirement blocks measured, 0 over).

## Gates, run by me from the CI workflow's own commands

Every command below was executed in this checkout on 2026-10-25 after the code
commit, with exit codes captured explicitly (not through a pipeline):

| Gate | Command | Result |
|---|---|---|
| pattern | `node scripts/guardrails-scan.mjs` | exit 0, 34 non-blocking warnings (pre-existing) |
| semantic | `node scripts/semantic-scan.mjs` | exit 0, clean (SEMANTIC-001, SEMANTIC-005) |
| regression + size | `python3 scripts/regression_check.py --base e5ba868 --fail-if-empty --pre-commit` | exit 0; 0 over hard limit |
| silent success | `bash scripts/silent-success-scan.sh` | exit 0 |
| failure registry | `python3 scripts/failure_registry_check.py` | exit 0 (stale-entry warnings only) |
| rules hygiene | `python3 scripts/rules_check.py` | exit 0 |
| exec bits | `python3 scripts/check_exec_bits.py` | exit 0, 118 shebang files at 100755 (the new test file was chmod'd after the gate caught it) |
| charset | `python3 scripts/check_charset.py --repo .` | exit 0, 850 files |
| encoding | `python3 scripts/check_encoding.py --repo .` | exit 0 |
| corruption content | `python3 scripts/check_corruption.py --repo .` | exit 0 |
| corruption range | `python3 scripts/check_corruption.py --repo . --range e5ba868..HEAD` | exit 0 (1456 added / 0 removed, 0 rewrites) |
| test floors | `python3 tests/gen_floors.py` | exit 0, 126 suites / 1784 tests |
| manifest joins | `python3 scripts/check_manifest_join.py --repo .` | exit 0 |
| artifact hygiene | `python3 scripts/artifact_hygiene.py --repo . --audit` | exit 0 |
| secret scan | `bash scripts/secret-scan.sh --repo . --range e5ba868..HEAD` | exit 0, 0 to fix |
| full suite | `python3 -m pytest tests/ -q` | 1784 passed, 182 subtests |
| openspec strict | `node_modules/.bin/openspec validate --all --strict` (pinned 1.14.3) | 45 passed, 0 failed |
| negative control | `bash scripts/specs-validate-negative-control.sh` | passed under the pinned CLI (refused its malformed fixture, missing `## Purpose`) |
| traceability | `python3 scripts/spec_traceability.py --root . --ratchet` | 139/182 covered, exit 0 |
| boundary | `python3 scripts/check_boundary.py --repo . [--changed-base origin/main]` | exit 0 both ways |

Traceability moved 133/176 -> 139/182 (all six new requirements covered) and
the ratchet floor was raised 133 -> 139 with `--update-ratchet`, which is the
mechanism the gate itself names; leaving the floor at 133 would let this
coverage evaporate silently.

**Not re-run locally, stated rather than implied:** the evaluator mutation
batteries, the benchmark corpus and the container-image job. This change
touches no `hub/`, coherence or evaluator code, so those jobs evaluate the
same bytes as the previous green run; CI runs them on the push.

## Mutation proofs

Each was applied to the committed file, measured, and reverted; the suite was
re-run after each revert (37 passed) and `git diff HEAD` was clean.

1. **The seed rule removed.** Deleting the `determinism.enabled` branch of
   `session_errors` failed exactly the two tests that own it
   (`test_play_under_determinism_without_a_seed_is_refused`,
   `..._with_a_blank_seed_is_refused`), 2 failed / 35 passed. A direct probe -
   a play manifest with no seed in a root whose `game-manifest.json` has
   `determinism.enabled: true` - then exited **0** where the contract requires
   **2**. The hard rule is load-bearing, not decorative.
2. **The gap count silenced.** Replacing `block["count"] = sum(...)` with a
   literal `0` failed four tests, including
   `test_the_gap_number_is_read_not_recomputed` - the test whose fixture root
   has no source files at all, so a rescan could not have produced the
   report's 7. The line is a read, not an inventory.

## Behaviour worth reading directly

- With a report at `.guardrails/spec-gap-report.json` claiming
  `unspaced 1 + partially_tracked 2 + uncovered_ids 4`, a work advisory prints
  `worst-tracked gaps: 7` and `worst: merge-engine [src/merge.gd:1-40]`;
  `claimed_but_absent: 1` contributes nothing, matching the scanner's own
  rail 3.
- With no report, the same line reads
  `worst-tracked gaps: unknown - no gap report at ...`, and the string
  `worst-tracked gaps: 0` does not appear.
- A report whose `root` is another tree reads unknown and names that tree.
- A play session with no `game-manifest.json` is refused (exit 2); a work
  session in the same root proceeds with `determinism: unknown`.

## Stated boundaries

1. **Nothing writes the report at its default path yet.** The documented
   producer is
   `python3 scripts/spec_gap_scan.py --root . --json > .guardrails/spec-gap-report.json`.
   Until a repository runs it (or CI publishes it as an artifact), the line
   honestly reads `unknown`. Running the scanner from the brain was rejected:
   it is exactly the second inventory box 4.2 forbids.
2. **The play-side screen-inventory block is a pointer, not a scan.**
   `scene_inventory.py` prints prose and returns an exit code; parsing it at
   session start would be a second implementation of "what the inventory
   found". The Godot hook delivery (rollout step 2) owns firing it.
3. **Phase gates are `unknown` by rule.** The phase matrix is `game-matrix-01`,
   marked planned, and no gate in this repository may claim its enforcement.
   Printing a list here would be that false claim.
4. **Out of scope, each its own delivery:** the Godot engine hook, the five
   carrier adapters, `docs/REDEYE-SESSION-CONTRACT.md`, `hub/sessions.py`
   ingestion. Nothing calls the brain until an adapter lands.
5. **Exit codes are inverted against the secret-scan family** (`2` refusal,
   `1` malfunction). That is deliberate and stated as requirement `session-06`
   so a runner reads it instead of assuming the families agree.

## Assumptions this evidence rests on

- The schema is the single statement of shape for fields, and the two
  conditionals are owned by the brain; the schema's description says so, and a
  test pins the capture conditional in both directions.
- The merged failure registry is AIGGP's bundled baseline plus the project
  overlay (`gate_overlay`), so advice in a consumer repo sees the consumer's
  entries; the session then lists only unresolved ones overlapping its scope.
- "Accepted" means the manifest validated and the rule passed - not that the
  work the session begins is correct. This block advises; it does not judge.
