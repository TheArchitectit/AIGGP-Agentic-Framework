# Spec: Gate execution contract

## Requirement: Project-root resolution
<!-- id: gate-root-01 -->
The system shall resolve the project root from the scanner's own location:
the parent directory of `.devgate/` when the scanner runs inside one, and the
scanner's own repository otherwise. No gate shall walk upward from the
script's parent directory searching for marker files.

#### Scenario: standalone checkout
- **WHEN** semantic-scan.mjs or run-tests.mjs runs in a DevGate checkout that
  is not inside a `.devgate/` directory
- **THEN** the scan targets the checkout itself and exits 0 after evaluating
  the checkout's own files

#### Scenario: submodule checkout
- **WHEN** any gate runs from `<project>/.devgate/scripts/`
- **THEN** the scan targets `<project>/` and never a sibling or ancestor of it

## Requirement: No vacuous green
<!-- id: gate-vacuous-01 -->
A gate that evaluated zero applicable inputs shall not report the same output
as a gate that evaluated its inputs and found them clean; when zero inputs is
a configuration error (test discovery found nothing in a project that has
tests), the gate shall fail with a diagnostic naming what it looked for.

#### Scenario: test runner finds no files
- **WHEN** run-tests.mjs discovers zero test files in a project containing
  files matching its documented test patterns
- **THEN** it exits non-zero with the searched roots in the message

#### Scenario: cargo filter matches no tests
- **WHEN** a Rust test target runs and cargo reports "running 0 tests"
- **THEN** the file is reported as failed, not passed

## Requirement: --all diff window
<!-- id: gate-allwindow-01 -->
Under `--all`, every scan arm (pattern rules, registry patterns, added-line
checks) shall evaluate the same diff window: added lines of `<base>...HEAD`,
where base is the most recent tag or the documented fallback.

#### Scenario: committed violation, clean tree
- **WHEN** a critical pattern violation was committed after the last tag and
  the working tree is clean
- **THEN** `regression_check.py --all --pre-commit` reports the violation and
  exits 1

#### Scenario: per-PR scoping
- **WHEN** `--base origin/main` is supplied
- **THEN** only added lines of `origin/main...HEAD` are scanned
