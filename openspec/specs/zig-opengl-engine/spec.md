# Zig + OpenGL Engine Support

Status: Proposed. Adds quality gates for Zig + OpenGL game projects.

## Overview

This spec extends devgate-game-framework to support Zig + OpenGL game projects.
It provides engine-specific scene inventory and regression scanning for Zig
codebases, complementing the existing Godot scanner.

## Engine Detection

The framework detects Zig + OpenGL projects via:

1. `game-manifest.json` with `"engine": "Zig + OpenGL"`
2. Presence of `build.zig` file

## Scene Inventory (Zig)

### Discovery
- Scans `.zig` files under `src/ui/` only (UI screens)
- Each file is a screen with entity definitions and handler functions

### Validation
1. **Screen export** — each UI file should export `init()`, `update()`, `render()`, `handle_input()`
2. **Button handler binding** — every button (`.label = "..."`) should have a connected handler (`.handler = "..."`)
3. **Orphan detection** — handler functions without connected buttons are flagged

### Excluded Functions
These internal functions are not considered orphaned:
- `init`, `update`, `render`, `handle_input`, `deinit`, `show`, `hide`
- `updateHUD`, `checkWarnings`, `showAnimation`, `initScreen`, `showScreen`, `hideScreen`

## Regression Patterns (Zig)

| ID | Type | Pattern | Description |
|---|---|---|---|
| Z001 | ZIG_COMPILE | `error:.*unexpected` | Compile-time error |
| Z002 | ZIG_UNWRAP | `\?\s$` | Unsafe unwrap at line end |
| Z003 | ZIG_MEMORY | `std\.mem\.alloc\(` | Actual allocation call |
| Z004 | OPENGL_CTX | `glGetError\(\)` | OpenGL error check |
| Z005 | SHADER_FAIL | `glCompileShader` | Shader compilation |
| Z006 | WASM_SIZE | `\.wasm` | WebAssembly build file |
| Z007 | ENTITY_LEAK | `\.destroy\(` | Entity destroy call |
| Z008 | AUDIO_DEV | `ma_engine_init` | Audio engine init |
| Z009 | INPUT_CAPTURE | `glfwSetKeyCallback` | Input callback registration |
| Z010 | WEB_GL | `emscripten_set_main_loop` | Emscripten main loop |

### Skeleton regressions (Z011-Z021)

Seeded from the Zombie Diver audit. Each records a way a Zig + OpenGL source tree
can look complete while executing nothing — the failure mode that let a "finished"
tree sit unchecked without ever compiling or rendering.

| ID | Type | Detects |
|---|---|---|
| Z011 | BUILD_ASSET_MISSING | `@embedFile` target absent from the tree |
| Z012 | DEP_BLOCKER | `defer` on a value whose type defines no `deinit` |
| Z013 | TYPE_UNDEFINED | enum member referenced but never declared |
| Z014 | NO_DRAW | geometry built but never uploaded or drawn |
| Z015 | SHADER_UNLINKED | program id returned without a compile/link status check |
| Z016 | VIEWPORT_HARDCODED | fixed window dimensions, no `glViewport` |
| Z017 | INPUT_UNPOLLED | GLFW polling/callbacks commented out |
| Z018 | COPY_MUTATE | value mutated through `HashMap.get()` instead of `getPtr()` |
| Z019 | HANDLER_UNRESOLVABLE | UI handler referenced as a string naming no real type |
| Z020 | ANIMATION_GROWTH | deactivated list entries never removed |
| Z021 | PLACEHOLDER_ROTATION | unconditional stand-in for real input |

Note on Z011/Z012: a regex cannot express "this file is missing" or "this type has
no such method". Their patterns pin the known defect *call sites*; the general class
is enforced by the compiler. This mirrors the deliberate deviation recorded for
`PREVENT-024` in radredeye — a regex cannot do a semantic check.

## Scan Scope (manifest-driven)

The scanner must not decide scope from a hardcoded directory list: it cannot know a
project's build layout, so it either reports findings inside cached dependencies
(which nobody can fix, so the gate gets ignored) or misses real source.

Projects declare their own exclusions in `game-manifest.json`:

```json
"scan": {
  "exclude_dirs": ["external", "zig-pkg", "zig-out", ".zig-cache", "spool"],
  "include_extensions": [".zig"]
}
```

Rules:
1. The scanner **unions** `exclude_dirs` with its built-in defaults. A project may
   add exclusions; it may not remove the defaults.
2. Exclusion matches whole path **components**, so `build` does not also match
   `build-system`.
3. A missing `scan` key is not an error — defaults apply, so existing projects keep working.

Without this, scanning Zombie Diver reports 14 findings inside
`zig-pkg/zgl-*/src/binding.zig`, a cached third-party package, and 0 in project code.


## Game-Class Patterns (shared)

These patterns from the Godot scanner also apply to Zig projects:

| ID | Type | Description |
|---|---|---|
| F008 | AIR_DEPLETE | Air resource drains unexpectedly |
| F009 | LIGHT_FAIL | Light source fails |
| F010 | STAMINA_BROKEN | Stamina system broken |
| F011 | ZOMBIE_PATHFIND | Zombie AI pathfinding failure |
| F012 | WATER_EFFECTS | Underwater effects broken |
| F013 | DEPTH_AMBIENT | Depth/atmosphere effects broken |

## Module Structure

```
devgate-game-framework/
├── engines/
│   ├── godot/                    # Godot engine support (existing)
│   └── zig-opengl/               # Zig + OpenGL engine support
│       ├── __init__.py
│       ├── scanner.py            # Zig screen scanner
│       ├── manifest.py           # Engine detection
│       └── patterns.json         # Zig regression patterns
├── scripts/
│   ├── scene_inventory.py        # Engine-aware dispatcher
│   └── game_regression.py        # Engine-aware dispatcher
└── openspec/specs/
    ├── zig-opengl-engine/        # This spec
    ├── game-type-phase-matrix/   # (add zig-opengl game types)
    ├── per-screen-tracking/      # (add zig screen tracking)
    └── game-regression/          # (add zig patterns)
```

## Usage

```bash
# Auto-detect engine and scan
python scripts/scene_inventory.py --all
python scripts/game_regression.py --all

# Pre-commit mode
python scripts/scene_inventory.py --staged --pre-commit
python scripts/game_regression.py --staged --pre-commit
```

## Reference Implementation

Zombie Diver (`TheArchitectit/Zombie-Diver`) is the reference implementation
for Zig + OpenGL engine support. All scripts have been tested against its
skeleton codebase.

## Seeding

Port from:
- `scripts/scene_inventory_zig.py` — Zig-adapted scene inventory
- `scripts/game_regression_zig.py` — Zig-adapted regression scanner
- `.guardrails/failure-registry.jsonl` — Zig-specific patterns (Z001-Z010)
