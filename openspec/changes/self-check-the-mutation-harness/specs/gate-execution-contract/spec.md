## ADDED Requirements

### Requirement: Verification harnesses are self-checked
<!-- id: gate-selfcheck-01 -->
A verification harness that decides whether a named test catches a deliberately
introduced defect SHALL be exercised against a case whose outcome is known by
construction, so that a harness which misreports fails a test rather than
turning a battery green. It SHALL distinguish three outcomes that otherwise
collapse into one: a defect the named test caught, a change no test can see, and
a mutation that was never applied or whose artifact no longer parses — neither
of the last two being evidence about any test.

#### Scenario: an unapplied mutation is not a kill
- **WHEN** a mutation's anchor text does not appear in its target file
- **THEN** the harness reports the anchor as unapplied and reports no verdict

#### Scenario: a syntax-breaking mutation is not a kill
- **WHEN** a mutation leaves the target file unparseable in its language
- **THEN** the run is reported INVALID and does not count as a killed mutant

#### Scenario: a negative control that dies fails the battery
- **WHEN** a mutation documented as one that must survive is caught by a test
- **THEN** the battery exits non-zero

### Requirement: Every mutation battery is run by the pipeline
<!-- id: gate-battery-ci-01 -->
Every mutation battery in the repository SHALL be executed by the continuous
integration pipeline, and a battery that no pipeline step names SHALL fail a
test rather than be silently unrun.

#### Scenario: a battery is added and never wired up
- **WHEN** a `tests/mutation_battery_*.py` file exists that the pipeline does
  not name
- **THEN** a test fails naming that file
