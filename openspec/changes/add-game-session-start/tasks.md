# Tasks: gameSessionStart (step 1)

Rollout step 1 of the approved design: spec + schema + brain + tests in AIGGP.
Every normative clause in the delta spec has a positive test and, where the
clause is a refusal or an honest-empty, a negative control. Nothing here is
marked complete from spec authoring.

## 1. Contract

- [x] 1.1 Freeze `aiggp.session/v1` as
      `.guardrails/prevention-rules/session-manifest.schema.json`, with the two
      conditionals named in its description and owned by the brain.
- [x] 1.2 Document `determinism.enabled` in the game-manifest contract with
      absent = off, so the seed rule lands with its field
      (`scripts/game-framework-README.md`).

## 2. The brain

- [x] 2.1 `scripts/game_session_start.py`: subset validator, the two
      conditionals, the seed rule, `--stdin` / `--manifest`, `--root`,
      `--gap-report`, `--json`.
- [x] 2.2 Advisory assembly, kind-filtered, deterministic, with honest-empty
      lines for phase gates, the pre-work-check pointer, screen inventory,
      registry hits and the gap line.
- [x] 2.3 Append-only log at `.guardrails/sessions.jsonl`, canonical rows,
      duplicates appended.

## 3. The gap line (the spec-audit rollout's last box)

- [x] 3.1 `worst-tracked gaps: N` read from the scanner's `--json` report;
      N is the `--fail-on-gaps` count; the brain never runs the scanner.
- [x] 3.2 Unknown for a missing, malformed or foreign report - never `0`.
      Proven by a report that says 7 in a root with no sources at all.

## 4. Tests and gates

- [x] 4.1 `tests/test_game_session_start.py`: 37 tests over the schema matrix,
      both conditionals, the determinism x seed matrix, kind filtering,
      honest-empty lines, log semantics and the exit-code contract.
- [x] 4.2 Floor row in `tests/expected-counts.json` (the manifest-join gate
      requires every collected suite to carry one).
- [ ] 4.3 Gate re-run record and the mutation proofs (seed rule removed,
      gap line re-pointed at a rescan) appended to the QA note.

## 5. Out of scope (rollout steps 2-5, each its own delivery)

- [ ] 5.1 Godot engine hook + play-side screen-inventory block.
- [ ] 5.2 Carrier adapters (Claude Code, pi-extension, Codex, OpenCode,
      MiMo) to the three-step adapter contract.
- [ ] 5.3 `docs/REDEYE-SESSION-CONTRACT.md` and the red-eye registry join.
- [ ] 5.4 `hub/sessions.py` ingestion of the session log.
- [ ] 5.5 A producer that writes the gap report at its default path.
