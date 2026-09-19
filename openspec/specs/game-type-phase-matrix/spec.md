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
