# Change: gameSessionStart - the session brain and its advisory

## Why

AIGGP has no session lifecycle. Work-sessions (an agent opening a game repo to
edit) and play-sessions (the game runtime booting a run) both start silently:
nothing emits context, nothing records that a session happened, and the
existing determinism policy ("an unseeded crash is not comparable") is only
enforced after a crash, when it is most expensive.

The design was approved for implementation planning on 2026-09-29
(`docs/superpowers/specs/2026-09-29-game-session-start-design.md`). Its
rollout order has five steps; this change is step 1 - spec, schema, brain and
tests in AIGGP. The engine hook, the five carrier adapters, the red-eye
session contract and `hub/sessions.py` ingestion are later deliveries, and
this change states that boundary instead of implying it lands here.

It also closes the last open box of the spec-audit rollout package: the
work-session advisory gains the `worst-tracked gaps: N` line fed by the gap
scanner's own JSON report, so the scanner the package built has exactly one
consumer and one inventory source.

## What Changes

- **One manifest contract** (`aiggp.session/v1`) as a JSON Schema under
  `.guardrails/prevention-rules/`, validated by a Draft-07 subset validator in
  the brain. The two rules the subset cannot express - a declared `capture`
  block requires a `stream_id`, and a `play` session under determinism
  requires a `seed` - are named in the spec and enforced in the brain.
- **One brain** (`scripts/game_session_start.py`): validate, apply the single
  hard rule, assemble the kind-filtered advisory block as lines and as JSON,
  and append accepted sessions to `.guardrails/sessions.jsonl`. Adapters stay
  thin; no rule lives in a carrier.
- **The advisory block**: phase and gates (honest `unknown` - the phase matrix
  is planned), determinism banner, scope-filtered registry hits, the
  pre-work-check pointer, the capture pointer or an honest `capture: none`,
  and the new `worst-tracked gaps: N` line read from the gap scanner's report.
- **The gap line never rescans.** It reads `.guardrails/spec-gap-report.json`
  (or `--gap-report`); a missing, malformed or foreign report renders
  `unknown`, never `0`. The brain does not run `spec_gap_scan.py`.
- **Determinism is declared, not assumed.** `determinism.enabled` is documented
  in the game-manifest contract (`scripts/game-framework-README.md`) with
  absent = off, so the seed rule is never dead code waiting on a producer.
- **Tests** (`tests/test_game_session_start.py`) pin every requirement:
  schema matrix, both conditionals, the determinism x seed matrix, kind
  filtering, honest-empty lines, log semantics and the exit-code contract.

## Capabilities

### New Capabilities

- `game-session-start`: the shared session manifest, the one boot-time hard
  rule, the advisory block and the append-only session log.

### Modified Capabilities

- None. `game-type-phase-matrix` is referenced by the advisory as `unknown`;
  its requirement (`game-matrix-01`) is untouched and stays planned.

## Impact

- New: `scripts/game_session_start.py`,
  `.guardrails/prevention-rules/session-manifest.schema.json`,
  `tests/test_game_session_start.py`.
- Edited: `scripts/game-framework-README.md` (the `determinism.enabled` field),
  `CHANGELOG.md`, `tests/expected-counts.json` (a floor row for the new suite;
  the manifest-join gate requires one).
- No consumer breaks by default: the seed rule is opt-in, and nothing calls the
  brain until a carrier adapter lands (step 3).
- Not in this change: Godot engine glue, the Claude Code / pi-extension /
  Codex / OpenCode / Xiaomi MiMo adapters, `docs/REDEYE-SESSION-CONTRACT.md`,
  `hub/sessions.py`, and a producer that writes the gap report to its default
  path.
