# Rule Coverage Truth

## Purpose

The traceability gate's summary must be arithmetically the same claim as its
own `--report` detail: one unit counted on both sides of the fraction.

## ADDED Requirements

### Requirement: The coverage summary counts statements on both sides
<!-- id: rule-denominator-01 -->
The coverage summary SHALL count requirement statements in both numerator and
denominator, including every restatement covered in the detailed report.
When an ID occurs more than once, the summary SHALL give the number of reused
IDs. An uncovered statement in a blocking capability SHALL still fail the
gate.

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
