# Scanner parsing correctness

## Purpose

Scanners parse their inputs correctly: diff hunks carry accurate line numbers, glob semantics match their documented fnmatch behavior, file-size classification distinguishes test files, and Godot text scenes are parsed by their real grammar.

## Requirements


### Requirement: Godot scene parsing
<!-- id: gate-tscn-01 -->
The scene inventory gate SHALL parse `.tscn` as Godot's text scene format
(not XML), SHALL associate signal connections with buttons by normalized
node name, and SHALL exit 0 for scenes whose buttons all have handlers.

#### Scenario: minimal valid scene
- **WHEN** a valid scene declares a Button with a `pressed` connection
- **THEN** the gate reports OK and exits 0

#### Scenario: nested button path
- **WHEN** a connection's `from` attribute is a node path (e.g.
  `Panel/PlayButton`)
- **THEN** it is matched to the Button node named `PlayButton` and not
  reported orphaned

#### Scenario: genuine orphan
- **WHEN** a Button has no `pressed` connection
- **THEN** the gate reports the orphan by name and exits 1

### Requirement: Rust test-scope exemption
<!-- id: gate-rstest-01 -->
Error/critical pattern rules SHALL not fire on lines inside `#[cfg(test)]`
modules, whether the module opens on the attribute line or the following
line, and reported line numbers SHALL remain accurate.

#### Scenario: single-line module opener
- **WHEN** a file contains `#[cfg(test)] mod tests {` and a later line inside
  the module matches a critical rule
- **THEN** no violation is reported for that line

#### Scenario: production line still gated
- **WHEN** the same pattern appears outside any `#[cfg(test)]` module
- **THEN** the violation is reported with its real line number

### Requirement: Test file sizing
<!-- id: gate-size-01 -->
The file-size gate SHALL discover test files in `tests/` and `test/`
directories and SHALL apply TEST_HARD to files matching test naming
(`test_*.py`, `*_test.py`, `_test.go`, `*.test.*`, `*.spec.*`, `*_test.rs`).

#### Scenario: pytest file over source limit
- **WHEN** `tests/test_big.py` has 550 lines
- **THEN** it is evaluated against TEST_HARD (600), not SRC_HARD (500)
