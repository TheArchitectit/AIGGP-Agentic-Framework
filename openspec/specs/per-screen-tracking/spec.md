# Per-screen feature tracking

## Purpose

The absorbed scene-inventory tooling lives in this framework as
`scripts/scene_inventory.py`: a static gate that parses Godot text scenes,
inventories Button nodes, and fails scenes whose `pressed` signals have no
connected handler. This spec covers that static inventory. Engine-execution
gates named by the original game-framework proposal — scene-load smoke runs,
node budgets, screen reachability, phase-matrix feature attribution — are
planned work for consuming game repos and are explicitly NOT implemented in
this repository.

## Requirements

### Requirement: Scene inventory and orphan detection
<!-- id: screen-inv-01 -->
The scene inventory gate SHALL discover `.tscn` scenes under the project's
`src/` and `scenes/` trees and root, parse them as Godot text scenes (per
gate-tscn-01), report every Button node and `pressed` connection, and exit 1
when any Button's `pressed` signal has no connected handler, naming the
orphan.

#### Scenario: fully wired scene passes
- **WHEN** every Button in a discovered scene has a `pressed` connection
- **THEN** the gate reports the scene OK and exits 0

#### Scenario: orphaned button fails the gate
- **WHEN** a Button has no `pressed` handler connection
- **THEN** the gate names the orphan and exits 1

### Requirement: Empty scene scope is not a pass
<!-- id: screen-inv-02 -->
When no `.tscn` files are discovered the gate SHALL print an explicit NOTHING
SCANNED notice rather than a clean pass; `--fail-if-empty` SHALL turn the
empty scope into exit 2 for CI, and the default empty-scope exit SHALL remain
0 so non-Godot consumers are not blocked.

#### Scenario: non-Godot repository
- **WHEN** the gate runs in a repository with no scenes
- **THEN** it prints NOTHING SCANNED and exits 0, or exits 2 with
  `--fail-if-empty`
