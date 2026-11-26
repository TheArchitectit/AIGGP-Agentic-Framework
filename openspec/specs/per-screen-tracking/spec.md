# Per-screen feature tracking

Status: Closed (2 of 2 requirements terminal 2026-10-19). `screen-inv-01`:
the gate in `scripts/scene_inventory.py` discovers `.tscn` scenes under
`src/`, `scenes/` and the project root, parses them as Godot text scenes (per
gate-tscn-01), reports every Button and `pressed` connection, and exits 1
naming the orphan. `screen-inv-02`: a zero-scene scope prints NOTHING SCANNED
rather than a clean pass, `--fail-if-empty` turns it into exit 2, and the
default empty-scope exit stays 0. Both halves are locked by
`tests/test_scene_inventory.py` (15 tests), including the QA C1 regression that
the parser reads Godot TEXT scenes and not XML. Neither requirement carried a
source marker before 2026-10-19, so `spec_traceability` reported them
UNCOVERED while the behaviour and the tests shipped; the markers now sit in
the scanner header and the ratchet floor moved 76 -> 78. The engine-execution
gates named in Purpose remain planned work for consuming game repos and are
explicitly NOT implemented here; they are not requirement IDs of this spec.

2026-10-25 — "no connected handler" includes the script-side wiring Godot's
editor and docs both produce (`$Panel/Btn.pressed.connect(f)`, or an
`@onready var btn = $Panel/Btn` followed by `btn.pressed.connect(f)`). Until
this date the gate read `.tscn` connection blocks only, so every code-wired
UI read as orphaned. Measured on MergeKingdom: 4 scenes / 8 correctly wired
buttons reported as orphans, while the very same run also masked five real
defects — three popups whose `@onready` paths pointed at nodes their scenes do
not have, so `_ready()` aborted before building the UI. The gate now resolves
the root node's Script ext_resource, reads that script, and counts those
connections; a script that wires a *different* node leaves the orphan in
place, and a commented-out `connect()` is not a handler (both pinned as
tests).

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

#### Scenario: handler wired from the scene's script
- **WHEN** a Button's `pressed` handler is connected in the scene's own script,
  directly through a `$` node path or through an `@onready` node reference
- **THEN** the gate counts the button as connected and does not report it as
  an orphan

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
