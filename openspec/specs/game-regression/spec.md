# Game Regression Tracking

Status: Proposed. Enforcement layer invoked by game-type-phase-matrix.

## Purpose

Track game-class runtime failures (null derefs, scene-load failures, save corruption, orphaned signals, determinism breaks, perf regressions) as an append-only project registry, and block changes that re-introduce a registered failure. The registry is shared by `scripts/log_failure.py` and the regression scanner.

## Requirements

### Requirement: failure registry is append-only

Game failures SHALL be recorded by appending one JSON object per failure to
`.guardrails/failure-registry.jsonl`; existing entries SHALL never be edited or
removed, because the registry is the audit trail of what this project already
knew how to break.

#### Scenario: duplicate append is honest

- **WHEN** a failure is logged twice
- **THEN** the file holds two entries and the scanner treats them as one pattern

### Requirement: registered patterns block staged changes

The regression scanner SHALL evaluate staged and unstaged changes against every
game-class pattern in the registry, and SHALL exit nonzero when a change matches
a blocking pattern.

#### Scenario: reintroduced null-deref pattern

- **WHEN** a staged change matches a registered `NULL_DEREF` pattern
- **THEN** the scanner exits nonzero with the registry entry cited

### Requirement: determinism evidence for gameplay crashes

A gameplay-crash registry entry SHALL record the seed and input trace of the run
that produced it, and the gate SHALL require a seed-logged replay before treating
any further divergence as a regression.

#### Scenario: unseeded crash is not comparable

- **WHEN** a crash is reported without seed or trace
- **THEN** the gate refuses to mark it a regression and demands a seeded replay

## Registry
Append-only `.guardrails/failure-registry.jsonl` — one JSON object per bug/failure.
Never edit existing entries; append only via `scripts/log_failure.py`.

Game-class patterns tracked (beyond generic DevGate):
- NULL_DEREF / NPE at runtime
- SCENE_LOAD_FAIL — scene fails to instantiate
- SAVE_CORRUPT — save/load round-trip breaks
- SCRIPT_ERROR — engine script runtime error
- ORPHAN_SIGNAL — button/signal with no handler
- DETERMINISM_BREAK — seeded run diverges
- PERF_REGRESSION — frame time / memory exceeds budget

## Regression scanner
`scripts/game_regression_check.py` — scans staged/unstaged changes against the registry
patterns + file-size limits + prevention rules. `--pre-commit` exits nonzero on blockers.
Soft-as-hard headroom: promote soft violations to blocking for files changed since prior
release tag (mirror DevGate regression_check.py).

## Determinism accommodation
A gameplay run is only a regression candidate if seed + input trace are logged. Gate requires
seed-logged replay for any gameplay-crash entry.

## Seeding
Port from reference: Sword of Hope `scripts/regression_check.py`, `.guardrails/failure-registry.jsonl`,
`prevention-rules`, `b8_polish_verify.py`. Generic byte/file-size logic stays in DevGate; this
module adds the game-class patterns and screen/save/determinism hooks.
