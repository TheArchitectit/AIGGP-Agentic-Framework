# Game-type phase matrix

## Purpose

The original phase-matrix proposal (per-game-type minimum screens, systems,
and gates per development phase, driven by a manifest) was written for the
game-framework repository and is NOT implemented anywhere in this tree: no
`game-version` flag, phase manifest reader, or per-cell gate enforcement
exists here. Per base-specs-01 this capability stays bundled and explicitly
marked planned; the consuming game repo owns its implementation. The gates the
matrix would invoke — per-screen inventory and game-class regression scanning
— exist and are specified separately (per-screen-tracking, game-regression).

## Requirements

### Requirement: Manifest-driven phase gate (planned)
<!-- id: game-matrix-01 -->
**Status: planned — not implemented in this repository.** When implemented,
the phase gate SHALL read the current game type and phase from a project
manifest, require every gate named by that phase's matrix row plus all prior
rows, and fail closed on an unknown game type. Until it lands, no gate in this
repository may claim phase-matrix enforcement.

#### Scenario: unknown game type fails closed
- **WHEN** the phase gate (once implemented) reads a manifest naming a game
  type absent from the matrix
- **THEN** it fails rather than guessing a row

#### Scenario: no false enforcement claim today
- **WHEN** any bundled document or gate output is inspected for phase-matrix
  enforcement
- **THEN** none claims it — the capability is marked planned and only the
  consuming game repo may implement it

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

## Model

Each cell lists required: screens, systems, and gates. Gate = the per-screen/regression
enforcement that must pass at that phase.

### Roguelike (reference: Sword of Hope)
| Phase | Required screens | Required systems | Gates |
|---|---|---|---|
| Prototype | core loop screen | seeded RNG, single run | per-screen smoke, determinism |
| Pre-Alpha | map, battle | procedural gen, permadeath | button validation, demo-loop |
| Alpha | shop, meta-progression | economy lock, save/load | save round-trip, perf budget |
| Beta | everything + codex/achievements | content complete, balance lock | regression, input/focus, demo-loop clean |
| Release | all live screens | zero SCRIPT errors | ALL gates green; <=500-line rule |

## Enforcement
- Phase gate = the most advanced gate required by the row, plus every gate to its left.
- `game-version` flag in the framework reads the current phase from a manifest and fails
  if any required gate is missing/red.
- Unknown game type => fails closed (must be added to matrix before gating).

## Origin
Derived from Sword of Hope OpenSpec prod-001..prod-015 + game-design requirements.
