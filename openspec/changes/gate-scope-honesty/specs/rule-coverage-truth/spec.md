# Rule Coverage Truth

## Purpose

The traceability gate's summary must be arithmetically the same claim as its
own `--report` detail: one unit counted on both sides of the fraction.

## ADDED Requirements

### Requirement: The coverage summary counts statements on both sides
<!-- id: rule-denominator-01 -->
The covered/total summary SHALL count requirement **statements** in its
numerator and its denominator alike, so a requirement id stated by more than
one spec file (a change package restating a sealed requirement) can never be
reported as covered by the detail and uncovered by the summary at the same
time. When any id is stated more than once, the summary line SHALL say how
many ids are reused, so a total above the unique-id count is legible without
reading the source. A blocking capability SHALL still fail while any statement
of an uncovered id exists.

#### Scenario: a delta restates a sealed, covered requirement

- **GIVEN** a sealed spec and a change package under a different capability
  name, both carrying `<!-- id: game-daily-04 -->`
- **AND** a source marker covers `game-daily-04`
- **WHEN** the gate runs
- **THEN** the summary reports `2/2 requirements covered`
- **AND** names that one id is stated by more than one spec
- **AND** no advisory "uncovered" line is printed

#### Scenario: a restated uncovered id still blocks

- **GIVEN** the same two statements of one id in a blocking capability
- **AND** no marker covers it
- **WHEN** the gate runs
- **THEN** the gate exits 1
- **AND** the failure list names that id once
