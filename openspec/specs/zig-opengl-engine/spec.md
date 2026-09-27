# Zig + OpenGL Engine Support

Status: Proposed. Adds quality gates for Zig + OpenGL game projects. Enforcement
layer invoked by game-type-phase-matrix, alongside the Godot scanner.

## Purpose

Extend the game gates to Zig + OpenGL projects: detect the engine, inventory UI
screens and their handler bindings, and scan Zig/OpenGL source for the regression
classes a "finished-looking" tree can hide. Prior to this, the scanners understood
Godot only; a Zig project with no `.tscn` files was reported as empty and passed.

## Requirements

### Requirement: engine detection follows the manifest then project files

The scanners SHALL detect the project engine from `game-manifest.json`'s `engine`
field, falling back to project markers (`project.godot` → Godot, `build.zig` →
Zig + OpenGL), and SHALL treat an unrecognized engine as `unknown` rather than
guessing, so both game gates agree on which pattern set applies.

#### Scenario: Zig project without a manifest

- **WHEN** a project has `build.zig` and no `game-manifest.json`
- **THEN** the scanners report engine `Zig + OpenGL` and apply the Zig pattern set

### Requirement: Zig UI screens are inventoried under src/ui

The scene inventory SHALL discover `.zig` screens under `src/ui/`, extract
`.label = "..."` buttons with their adjacent `.handler = "..."` bindings, and
treat a non-internal function that no button references as an orphaned handler
that fails the gate.

#### Scenario: handler with no connecting button

- **WHEN** a `src/ui/` screen declares a function that no `.label` button binds
- **THEN** the gate fails and names the screen and the orphaned handler

### Requirement: scan scope is declared by the project manifest

The regression scanner SHALL union the project's `scan.exclude_dirs` with its
built-in defaults (a project may add exclusions, never remove them), match
exclusions on whole path components, and SHALL treat a missing `scan` key as
"defaults apply" rather than an error, so cached third-party trees do not report
findings nobody can fix.

#### Scenario: vendored cache excluded

- **WHEN** a project excludes `zig-pkg/` in `game-manifest.json`
- **THEN** findings inside the vendored package are not reported

### Requirement: Zig + OpenGL regression classes block staged changes

The regression scanner SHALL apply the Zig + OpenGL pattern classes
(`ZIG_COMPILE`, `ZIG_MEMORY`, `OPENGL_CTX`, `SHADER_FAIL`, `INPUT_CAPTURE`) to
scanned source and SHALL exit nonzero under `--pre-commit` when a change matches
a blocking pattern, with the pattern named.

#### Scenario: compile error pattern reintroduced

- **WHEN** a staged `.zig` change matches a `ZIG_COMPILE` pattern
- **THEN** the scanner exits nonzero and cites the match

## Engine detection

The framework detects Zig + OpenGL projects via:

1. `game-manifest.json` with `"engine": "Zig + OpenGL"`
2. Presence of a `build.zig` file

## Scene inventory (Zig)

- Discovery: `.zig` files under `src/ui/` only (UI screens). A project may declare
  `scan.non_screen_files` in its manifest for container/dispatch files that are
  legitimately not button-connected.
- Validation: buttons (`.label = "..."`) must bind a handler (`.handler = "..."`);
  handler functions without a bound button are orphaned and fail the gate.
- Excluded internal functions (never orphaned): `init`, `update`, `render`,
  `handle_input`, `deinit`, `show`, `hide`, `updateHUD`, `checkWarnings`,
  `showAnimation`, `initScreen`, `showScreen`, `hideScreen`.

## Regression patterns (Zig)

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

Skeleton regressions (Z011-Z021) are seeded from the Zombie Diver audit; their
patterns pin known defect call sites. A regex cannot express "this file is
missing" or "this type has no such method" — the general class is enforced by the
compiler, mirroring the deliberate deviation recorded for `PREVENT-024`.

## Module structure

```
engines/zig-opengl/
├── __init__.py
├── scanner.py      # Zig screen scanner
├── manifest.py     # Engine detection + manifest reader
└── patterns.json   # Zig regression patterns
openspec/specs/
└── zig-opengl-engine/   # This spec
```

## Reference implementation

Zombie Diver (`TheArchitectit/Zombie-Diver`) is the reference Zig + OpenGL
implementation; the scanners were tested against its skeleton codebase.

## Provenance

Imported from the former `devgate-game-framework` repository (source head
`4b69262`), merged into this repository 2026-09-26.
