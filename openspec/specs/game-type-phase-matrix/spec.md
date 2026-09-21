# Game-Type Phase Matrix

Status: Proposed. Keystone spec — drives all other devgate-game-framework gates. Defines the
minimum required features, screens, and verification per game type × phase.

## Purpose

Define the minimum required screens, systems, and verification gates for each
game type at each development phase, as a matrix the release gates read. The
matrix is the keystone: per-screen tracking and regression tracking attach their
enforcement to its rows.

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

## Requirements

### Requirement: phase gating follows the matrix row

The framework SHALL read the project's current phase from its manifest, and a
release gate run SHALL fail when any gate required by that phase's matrix row —
or any gate to its left — is missing or red.

#### Scenario: phase ahead of its gates

- **WHEN** the manifest declares Beta but the regression gate has no result
- **THEN** the gate run fails with the missing required gate named

### Requirement: unknown game types fail closed

A project whose game type is not present in the matrix SHALL fail the gate rather
than receive an empty (passing) requirement set, so the matrix cannot be silently
bypassed by declaring an invented type.

#### Scenario: invented type

- **WHEN** the manifest declares a game type with no matrix row
- **THEN** the gate run fails and names the type as unregistered

## Origin
Derived from Sword of Hope OpenSpec prod-001..prod-015 + game-design requirements.
