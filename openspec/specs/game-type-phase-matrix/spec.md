# Game-type phase matrix

Status: DEFERRED — NOT IMPLEMENTED (3 planned requirements; no gate in this
tree enforces any of them).

## Purpose

The original phase-matrix proposal (per-game-type minimum screens, systems,
and gates per development phase, driven by a manifest) was written for the
game-framework repository and is NOT implemented anywhere in this tree: no
`game-version` flag, phase manifest reader, or per-cell gate enforcement
exists here. Per base-specs-01 this capability stays bundled and explicitly
marked planned; the consuming game repo owns its implementation. The gates the
matrix would invoke — per-screen inventory and game-class regression scanning
— exist and are specified separately (per-screen-tracking, game-regression).
The reference matrix and the planned gate contract live with the rest of the
unbuilt game-repo work in `scripts/game-framework-README.md` ("What does NOT
ship here").

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

### Requirement: Phase gating follows the matrix row (planned — NOT IMPLEMENTED)
<!-- id: game-matrix-02 -->
**Status: planned — not implemented in this repository.** When implemented,
the release gate SHALL read the project's current phase from its manifest and
SHALL fail when any gate required by that phase's matrix row — or any gate to
its left — is missing or red. Until it lands, no run in this repository may
claim phase gating.

#### Scenario: phase ahead of its gates

- **WHEN** the phase gate (once implemented) reads a manifest declaring Beta
  but the regression gate has no result
- **THEN** the gate run fails with the missing required gate named

### Requirement: Unknown game types fail closed (planned — NOT IMPLEMENTED)
<!-- id: game-matrix-03 -->
**Status: planned — not implemented in this repository.** When implemented, a
project whose game type is not present in the matrix SHALL fail the gate
rather than receive an empty (passing) requirement set, so the matrix cannot
be silently bypassed by declaring an invented type.

#### Scenario: invented type

- **WHEN** the phase gate (once implemented) reads a manifest declaring a game
  type with no matrix row
- **THEN** the gate run fails and names the type as unregistered

## Origin

Derived from Sword of Hope OpenSpec prod-001..prod-015 + game-design
requirements. The reference Roguelike matrix (screens, systems, and gates per
phase) moved to `scripts/game-framework-README.md` with the rest of the
planned, unbuilt game-repo work.
