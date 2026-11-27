# Gate Execution Contract

## Purpose

A gate's green must be attributable to something it measured. Silence is not
scope, and a consumer should not have to reconstruct a tool's input in yaml to
avoid a vacuous pass.

## ADDED Requirements

### Requirement: A gate prints its own scope line on every exit path
<!-- id: gate-scope-line-01 -->
A hygiene gate that reports findings only when it has them SHALL also print a
scope line naming what it evaluated, on **every** exit path including success
and its early refusals. The line SHALL precede the findings so a wrapper
requiring it cannot be satisfied by a finding that happens to mention a count.

#### Scenario: a clean registry run

- **WHEN** `failure_registry_check.py` validates a merged registry with no
  findings
- **THEN** it exits 0
- **AND** stdout begins with `failure-registry: scope:`
- **AND** the line states the merged entry count and the per-source split

#### Scenario: the named registry does not exist

- **WHEN** `FAILURE_REGISTRY_PATH` points at a missing file
- **THEN** the gate exits 1
- **AND** the scope line still prints, recording zero entries and the reason

#### Scenario: a consumer requires the line

- **WHEN** a CI step greps the step output for the tool's scope line instead of
  counting registry files itself
- **THEN** the guard passes on a green run and fails on a run that scanned
  nothing, without the workflow knowing anything about merge semantics
