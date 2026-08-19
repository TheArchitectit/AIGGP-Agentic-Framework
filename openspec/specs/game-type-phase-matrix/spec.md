# Game-Type Phase Matrix

Status: Proposed. Keystone spec — drives all other devgate-game-framework gates. Defines the
minimum required features, screens, and verification per game type × phase.

## Model

Phases: Prototype -> Pre-Alpha -> Alpha -> Beta -> Release (Gold) -> Post-release.

Game types (extensible): roguelike, rpg, platformer, fps/twin-stick, strategy/tactics,
puzzle, visual-novel/story, sandbox/sim, idle/incremental.

## Matrix (required minimum per cell)

Each cell lists required: screens, systems, and gates. Gate = the per-screen/regression
enforcement that must pass at that phase.

### Roguelike (reference: Sword of Hope)
| Phase | Required screens | Required systems | Gates |
|---|---|---|---|
| Prototype | core loop screen | seeded RNG, single run | per-screen smoke, determinism |
| Pre-Alpha | map, battle | procedural gen, permadeath | button validation, demo-loop |
| Alpha | shop, meta-progression | economy lock, save/load | save round-trip, perf budget |
| Beta | everything + codex/achievements | content complete, balance lock | regression, input/focus, demo-loop clean |
| Release | all live screens | zero SCRIPT errors | ALL gates green; ≤500-line rule |

## Enforcement
- Phase gate = the most advanced gate required by the row, plus every gate to its left.
- `game-version` flag in the framework reads the current phase from a manifest and fails
  if any required gate is missing/red.
- Unknown game type => fails closed (must be added to matrix before gating).

## Origin
Derived from Sword of Hope OpenSpec prod-001..prod-015 + game-design requirements.
