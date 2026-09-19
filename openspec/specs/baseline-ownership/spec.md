# Baseline data ownership

## Purpose

Every file bundled in this repository is owned, accurate, and free of foreign-project data: bundled entries reference only paths that exist in this tree, leftover documents from absorbed projects are rewritten or removed, and instance data never ships in the baseline.

## Requirements


### Requirement: Baseline contains only this repo's data
<!-- id: base-own-01 -->
Every entry in a bundled baseline data file (failure registry,
silent-success allowlist, prevention rules, openspec specs) SHALL reference
only paths, bugs, and capabilities of this repository; a hygiene gate SHALL
fail when a bundled entry references a path absent from this tree.

#### Scenario: foreign allowlist entry
- **WHEN** a bundled allowlist entry's `file` does not exist in this repo
- **THEN** the baseline-hygiene check fails naming the entry

#### Scenario: clean checkout is warning-free
- **WHEN** failure_registry_check.py runs on a clean clone
- **THEN** it exits 0 with no stale-path warnings

### Requirement: Project bugs land in the project overlay
<!-- id: base-write-01 -->
In a submodule layout, tools that append to the failure registry SHALL write
the project's overlay file by default; writing the shared baseline SHALL
require an explicit flag, and the tool SHALL report which file received the
entry.

#### Scenario: default append in consumer
- **WHEN** log_failure.py runs in `<project>/.devgate/` without flags
- **THEN** the entry lands in `<project>/.guardrails/failure-registry.jsonl`
  and the output names that path

#### Scenario: explicit upstream append
- **WHEN** log_failure.py runs with `--upstream`
- **THEN** the entry lands in the DevGate baseline

### Requirement: Game-dev gates and specs live in this framework
<!-- id: base-specs-01 -->
Game development is part of this framework — one DevGate, not two (owner
decision 2026-09-13). Bundled game specs SHALL carry requirement IDs
traceable by spec_traceability.py, SHALL reference only gates that exist
in this repo or are explicitly marked planned, and no bundled document
SHALL direct readers to a separate game-framework repository. Game
gates (game_regression.py, scene_inventory.py) and their specs remain
here permanently.

#### Scenario: traceable bundled specs
- **WHEN** spec_traceability.py runs against the repo's bundled specs
- **THEN** every spec carries requirement IDs the gate can parse (no 0/0
  capabilities)

#### Scenario: no external game-framework pointer
- **WHEN** scripts/game-framework-README.md or any bundled spec is read
- **THEN** it documents the game tooling as part of this repo and contains
  no instruction to submodule a separate devgate-game-framework
  repository
