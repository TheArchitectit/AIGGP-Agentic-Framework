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
| `scripts/game_regression.py` | `game-regression` | Game-class failure patterns (NULL_DEREF, SCENE_LOAD_FAIL, SAVE_CORRUPT, ORPHAN_SIGNAL; SCRIPT_ERROR retired 2026-10-25 as `push_error`/`assert` noise) whose rules may name a guard (`(regex, guard, window)`) so the check written on the next line is not reported as the bug, plus failure-registry patterns with `file_glob` scoping, `guardrails-allow` annotations, and `.guardrailsignore` support; whole-line comments are never scanned. Empty scopes print NOTHING SCANNED; `--fail-if-empty` exits 2 for CI. |
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

## Session start (`game_session_start.py`)

Every session - an agent opening the repo to edit, or the runtime booting a
run - is described by one `aiggp.session/v1` manifest and judged by
`scripts/game_session_start.py` (schema:
`.guardrails/prevention-rules/session-manifest.schema.json`, spec:
`openspec/changes/add-game-session-start/`). The advisory block it prints
states `unknown` explicitly for any block it could not evaluate. A `work`
session's block carries a `worst-tracked gaps: N` line read from the gap
scanner's own JSON report - produced with

```bash
python3 .devgate/scripts/spec_gap_scan.py --json > .guardrails/spec-gap-report.json
```

The brain never runs the scanner itself: one inventory source. Without a
report the line reads `unknown`, never `0`.

Exit codes are inverted against the secret-scan family: `2` refused a known
session, `1` the brain cannot say, `0` accepted. Read the spec before wiring
either family into a pipeline.

### `determinism.enabled` in `game-manifest.json`

The one hard session rule reads this key:

| value | play-session |
|---|---|
| `true` | must carry a non-empty `seed`; refused (exit 2) without one |
| `false` | the rule is off |
| absent | the rule is off - a project opts in by declaring it |

A value that is present and is not a boolean is not read as a policy: the
brain exits 1 rather than guess whether a run is comparable. A `play` session
in a root with no `game-manifest.json` is refused; a `work` session in that
root proceeds with `determinism: unknown`.

## Provenance

The former standalone `devgate-game-framework` repository was merged into this
repository on 2026-09-26 (source head `4b69262`); its engine-aware scanners were
folded into the hardened in-tree scanners and its Zig + OpenGL module and spec
were imported under `engines/` and `openspec/specs/zig-opengl-engine/`.

Reference implementations: Sword of Hope (Godot), Zombie Diver (Zig + OpenGL).
