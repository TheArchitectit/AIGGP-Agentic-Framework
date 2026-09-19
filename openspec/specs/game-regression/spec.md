# Game-class regression scanning

## Purpose

The absorbed game tooling lives in this framework as `scripts/game_regression.py`:
a registry-pattern scanner that knows the game-specific failure classes
(dereference of unchecked node lookups, swallowed scene-load errors, save
corruption signatures, engine-script errors, orphaned button signals) on top of
the generic regression machinery. This spec describes what that scanner
actually enforces; game-framework machinery that lives in consuming game repos
(determinism harnesses, phase matrices, engine-execution smoke runs) is out of
scope here.

## Requirements

### Requirement: Game-class pattern scan
<!-- id: game-reg-01 -->
The game regression scanner SHALL scan changed or discovered source files
against its built-in game-class pattern families (NULL_DEREF, SCENE_LOAD_FAIL,
SAVE_CORRUPT, SCRIPT_ERROR, ORPHAN_SIGNAL) and SHALL report each hit with
pattern class, file, and line. With `--pre-commit` it SHALL exit non-zero when
any issue is found.

#### Scenario: orphaned signal detected
- **WHEN** a scanned source line connects a `pressed` signal in the pattern
  family ORPHAN_SIGNAL targets
- **THEN** the scanner reports the ORPHAN_SIGNAL hit with file and line

#### Scenario: pre-commit blocking
- **WHEN** the scanner runs with `--pre-commit` and finds issues
- **THEN** it exits 1 after printing the summary

### Requirement: Registry patterns honor scoping and annotations
<!-- id: game-reg-02 -->
Registry-sourced regression patterns SHALL apply only to files matching their
`file_glob`, SHALL skip lines carrying a matching `guardrails-allow`
annotation, and SHALL honor the project's `.guardrailsignore`; a `*.go`-scoped
registry pattern SHALL not fire on a markdown file quoting it.

#### Scenario: glob-scoped registry pattern
- **WHEN** a registry entry is scoped `file_glob: ["*.go"]` and a `.md` file
  quotes its pattern
- **THEN** the scanner does not report the markdown file

#### Scenario: annotated line suppressed
- **WHEN** a line carries `// guardrails-allow FAIL-<id>: <reason>` for the
  matching registry pattern
- **THEN** the scanner does not report that line

### Requirement: Empty scope is not a pass
<!-- id: game-reg-03 -->
When the scan scope evaluates zero files the scanner SHALL print an explicit
NOTHING SCANNED notice and never a clean-pass line; `--fail-if-empty` SHALL
turn the empty scope into exit 2 for CI, and the default empty-scope exit
SHALL remain 0 so non-game consumers are not blocked.

#### Scenario: empty project
- **WHEN** the scanner runs against a project with no matching source files
- **THEN** it prints NOTHING SCANNED and exits 0, or exits 2 with
  `--fail-if-empty`
