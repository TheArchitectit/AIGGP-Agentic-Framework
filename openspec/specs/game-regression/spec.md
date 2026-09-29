# Game-class regression scanning

## Purpose

Track game-class runtime failures (null derefs, scene-load failures, save corruption, orphaned signals, determinism breaks, perf regressions) as an append-only project registry, and block changes that re-introduce a registered failure. The registry is shared by `scripts/log_failure.py` and the regression scanner: an append-only `.guardrails/failure-registry.jsonl` — one JSON object per bug/failure, never edited, only appended via `scripts/log_failure.py`.

## Requirements

### Requirement: failure registry is append-only

Game failures SHALL be recorded by appending one JSON object per failure to
`.guardrails/failure-registry.jsonl`; existing entries SHALL never be edited or
removed, because the registry is the audit trail of what this project already
knew how to break.

#### Scenario: duplicate append is honest

- **WHEN** a failure is logged twice
- **THEN** the file holds two entries and the scanner treats them as one pattern

### Requirement: registered patterns block staged changes

The regression scanner SHALL evaluate staged and unstaged changes against every
game-class pattern in the registry, and SHALL exit nonzero when a change matches
a blocking pattern.

#### Scenario: reintroduced null-deref pattern

- **WHEN** a staged change matches a registered `NULL_DEREF` pattern
- **THEN** the scanner exits nonzero with the registry entry cited

### Requirement: determinism evidence for gameplay crashes

A gameplay-crash registry entry SHALL record the seed and input trace of the run
that produced it, and the gate SHALL require a seed-logged replay before treating
any further divergence as a regression.

#### Scenario: unseeded crash is not comparable

- **WHEN** a crash is reported without seed or trace
- **THEN** the gate refuses to mark it a regression and demands a seeded replay

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
