# Game-development tooling in DevGate

Game-development quality gates are part of THIS framework — one DevGate, not
two (baseline-ownership `base-specs-01`). There is no separate
`devgate-game-framework` repository to submodule; the tooling below ships here
and is specified under `openspec/specs/`.

## What ships here

| Tool | Spec | What it enforces |
|---|---|---|
| `scripts/game_regression.py` | `game-regression` | Game-class failure patterns (NULL_DEREF, SCENE_LOAD_FAIL, SAVE_CORRUPT, SCRIPT_ERROR, ORPHAN_SIGNAL) plus failure-registry patterns with `file_glob` scoping, `guardrails-allow` annotations, and `.guardrailsignore` support. Empty scopes print NOTHING SCANNED; `--fail-if-empty` exits 2 for CI. |
| `scripts/scene_inventory.py` | `per-screen-tracking` | Static Godot `.tscn` inventory: discovers scenes under `src/` and `scenes/`, parses the text-scene grammar, reports Buttons whose `pressed` signal has no connected handler. |
| `openspec/specs/game-type-phase-matrix/` | `game-matrix-01` | **Planned, not implemented here** — the manifest-driven per-phase gate is owned by the consuming game repo. |

## What does NOT ship here

Engine-execution gates (scene-load smoke runs, node budgets, screen
reachability, determinism harnesses, demo-loop verification) are game-repo
work: they need the engine and the game itself. This framework contributes the
static scanners above and the generic gate machinery
(`regression_check.py`, `guardrails-scan.mjs`, the failure registry) that a
game repo layers its own gates onto.

## Using the game gates in a game repo

Embed DevGate as `.devgate/` (see README), then run the scanners against your
tree — they auto-detect the project root by layout contract:

```bash
python3 .devgate/scripts/game_regression.py --staged --pre-commit
python3 .devgate/scripts/scene_inventory.py --fail-if-empty
```

Record game bugs with `scripts/log_failure.py` so
`regression_check.py` blocks their reintroduction (game-class entries and
their `regression_pattern`s work exactly like every other registry entry).
