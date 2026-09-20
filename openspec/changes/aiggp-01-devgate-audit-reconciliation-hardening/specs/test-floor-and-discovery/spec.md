## Requirement: nonzero test floor

The test gate SHALL fail EMPTY when test discovery returns zero tests, and SHALL report the discovered count in its result.

### Scenario: zero tests discovered

Given a repo where discovery finds no tests (the current run-tests behavior), when the gate runs, then it SHALL NOT exit green and SHALL state that zero tests were discovered.

## Requirement: bootstrap from clean clone

Gates SHALL run from a clean clone with documented bootstrap (dependencies installed, discovery working), and CI SHALL prove this on a fresh container.

### Scenario: missing pytest in environment

Given an environment lacking the test runner, when the gate runs, then it SHALL fail ERROR with a bootstrap diagnostic, not green.
