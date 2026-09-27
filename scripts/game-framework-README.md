# Game-development gates (part of this repository)

Game-development quality gates for AI-assisted game builds. These gates are part
of DevGate/AIGGP — one framework, not two (owner decision 2026-09-13) — and
shipped in this repository:

- `scripts/game_regression.py` — game-class regression scanner (engine-aware:
  Godot / Zig + OpenGL).
- `scripts/scene_inventory.py` — scene inventory + button/handler validation
  (engine-aware).
- `engines/zig-opengl/` — Zig + OpenGL engine module (scanner, manifest reader,
  pattern table).
- `openspec/specs/` — bundled game specs: `game-type-phase-matrix`,
  `per-screen-tracking`, `game-regression`, `zig-opengl-engine`.

## Modules
- **Game-Type Phase Matrix** — minimum required features/screens/verification per game type × phase (Prototype→Alpha→Beta→Release→Post-release)
- **Per-Screen Feature Tracking + Button Validation** — scene inventory, node/button registry, scene-load smoke, orphaned-signal detection
- **Game Regression Tracking** — failure-registry + regression scanner scaled to gameplay/crash/save-corruption patterns

## Usage

Consumers vendor this repository (submodule or checkout) and run the gates
from their project root; engine detection reads `game-manifest.json`.

```bash
python scripts/scene_inventory.py --all
python scripts/game_regression.py --all
```

## Provenance

The former standalone `devgate-game-framework` repository was merged into this
repository on 2026-09-26 (source head `4b69262`); its engine-aware scanners were
folded into the hardened in-tree scanners and its Zig + OpenGL module and spec
were imported under `engines/` and `openspec/specs/zig-opengl-engine/`.

Reference implementations: Sword of Hope (Godot), Zombie Diver (Zig + OpenGL).
