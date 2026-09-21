# Per-Screen Feature Tracking + Button Validation

Status: Proposed. Enforcement layer invoked by game-type-phase-matrix.

## Purpose

Keep an inventory of every game screen and interactive control, and fail the gate
when a control has no handler or a phase-required screen does not exist — the two
failure modes players see as dead buttons and missing content.

## Inventory
Every game screen = each .tscn scene. Scanner builds/manages:
- `scenes.json` — scene path, node tree hash, screen role (menu/combat/map/shop/etc).
- `buttons.json` — per scene, every Button node + its `pressed` handler binding.

## Gates (fail closed)
1. **Scene-load smoke** — every scene instantiates clean, 0 SCRIPT ERRORs, no orphan resources.
2. **Button handler validation** — every Button has a connected/signaled handler; orphaned
   `pressed` signals (signal declared, no connected handler) are a blocking failure.
3. **Node budget** — per-scene node count within band (config); oversized scenes fail.
4. **Screen reachability** — every screen reachable via navigation (no unreachable scenes).
5. **Feature-per-screen attribution** — each phase-matrix required screen maps to a real scene;
   missing required screen at that phase => gate red.

## Seeding
Port from reference: Sword of Hope `scene_load_check.gd`, `integration_runner.gd`, `demo_manager_screens.gd`.
Detect engine flavor (Godot .tscn / Bevy / Unity) from the manifest and use the matching scanner.

## Requirements

### Requirement: every button carries a live handler

The scanner SHALL record every interactive control per scene, and a control with
no connected handler SHALL be a blocking gate failure — an orphaned signal ships
as a dead button the player can press with no effect.

#### Scenario: orphaned pressed signal

- **WHEN** a `.tscn` scene declares a Button whose `pressed` signal connects to nothing
- **THEN** the gate fails and names the scene and control

### Requirement: required screens exist at their phase

Every screen required by the project's current game-type phase-matrix row SHALL
map to a real scene in the inventory, and a missing required screen SHALL make
the gate red.

#### Scenario: matrix demands an unbuilt screen

- **WHEN** the Alpha row requires a shop screen and no scene is registered with that role
- **THEN** the gate fails citing the missing required screen
