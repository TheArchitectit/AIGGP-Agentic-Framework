# Per-Screen Feature Tracking + Button Validation

Status: Proposed. Enforcement layer invoked by game-type-phase-matrix.

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
