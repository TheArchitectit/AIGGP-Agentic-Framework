# Game-development gates (part of this repository)

Game-development quality gates are part of DevGate/AIGGP — one framework, not
two (owner decision 2026-09-13; baseline-ownership `base-specs-01`). There is
no separate `devgate-game-framework` repository to submodule; the tooling
below ships here and is specified under `openspec/specs/`:

- `scripts/game_regression.py` — game-class regression scanner (engine-aware:
  Godot / Zig + OpenGL).
- `scripts/scene_inventory.py` — scene inventory + button/handler validation
  (engine-aware).
- `engines/zig-opengl/` — Zig + OpenGL engine module (scanner, manifest reader,
  pattern table).
- `openspec/specs/` — bundled game specs: `game-type-phase-matrix`,
  `per-screen-tracking`, `game-regression`, `zig-opengl-engine`.

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

## Usage

Consumers vendor this repository (submodule or `.devgate/` checkout) and run
the gates from their project root; engine detection reads
`game-manifest.json`. All scripts auto-detect the project root by layout
contract (the parent of `.devgate/`, or the checkout itself).

```bash
python3 .devgate/scripts/game_regression.py --staged --pre-commit
python3 .devgate/scripts/scene_inventory.py --fail-if-empty
# or, from a vendored checkout at the project root:
python scripts/scene_inventory.py --all
python scripts/game_regression.py --all
```

Record game bugs with `scripts/log_failure.py` so `regression_check.py`
blocks their reintroduction (game-class entries and their
`regression_pattern`s work exactly like every other registry entry).

## Provenance

The former standalone `devgate-game-framework` repository was merged into this
repository on 2026-09-26 (source head `4b69262`); its engine-aware scanners were
folded into the hardened in-tree scanners and its Zig + OpenGL module and spec
were imported under `engines/` and `openspec/specs/zig-opengl-engine/`.

Reference implementations: Sword of Hope (Godot), Zombie Diver (Zig + OpenGL).
