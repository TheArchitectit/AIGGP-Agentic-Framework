# Spec: Baseline data ownership

## Requirement: Baseline contains only this repo's data
<!-- id: base-own-01 -->
Every entry in a bundled baseline data file (failure registry,
silent-success allowlist, prevention rules, openspec specs) shall reference
only paths, bugs, and capabilities of this repository; a hygiene gate shall
fail when a bundled entry references a path absent from this tree.

#### Scenario: foreign allowlist entry
- **WHEN** a bundled allowlist entry's `file` does not exist in this repo
- **THEN** the baseline-hygiene check fails naming the entry

#### Scenario: clean checkout is warning-free
- **WHEN** failure_registry_check.py runs on a clean clone
- **THEN** it exits 0 with no stale-path warnings

## Requirement: Project bugs land in the project overlay
<!-- id: base-write-01 -->
In a submodule layout, tools that append to the failure registry shall write
the project's overlay file by default; writing the shared baseline shall
require an explicit flag, and the tool shall report which file received the
entry.

#### Scenario: default append in consumer
- **WHEN** log_failure.py runs in `<project>/.devgate/` without flags
- **THEN** the entry lands in `<project>/.guardrails/failure-registry.jsonl`
  and the output names that path

#### Scenario: explicit upstream append
- **WHEN** log_failure.py runs with `--upstream`
- **THEN** the entry lands in the DevGate baseline

## Requirement: Game-specific specs live with the game framework
<!-- id: base-specs-01 -->
The language-agnostic framework shall not bundle capability specs for a
specific game framework; remaining game-oriented scanners shall be
documented as generic Godot tooling.

#### Scenario: traceable bundled specs
- **WHEN** spec_traceability.py runs against the repo's bundled specs
- **THEN** every spec carries requirement IDs the gate can parse (no 0/0
  capabilities)
