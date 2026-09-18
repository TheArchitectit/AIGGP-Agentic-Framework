# Tasks: fix-size-gate-test-scope

Conformance fix for FAIL-f6228dda against `scanner-parsing` gate-size-01
(no spec deltas — implementation only, `skip_specs: true`).

## Sprint 1 — self-test first (prevention_rule: feed the gate a file it MUST flag)

- [ ] 1.1 `tests/test_regression_sizes.py`: known-oversize pytest fixture
      (`tests/test_giant.py`, TEST_HARD+1 lines) through `check_file_sizes`'
      own API — must be flagged with `hard == TEST_HARD` (600), proving test
      classification and that the fixture directory is really evaluated
- [ ] 1.2 Same file: the gate-size-01 scenario — a 550-line pytest file must
      NOT be flagged (TEST_HARD 600, not SRC_HARD 500)
- [ ] 1.3 Matcher contrast: a non-test `.py` file at SRC_HARD+1 lines must be
      flagged at `hard == SRC_HARD` while the same-size `test_*.py` file is not
- [ ] 1.4 Scope-list assertion: `regression_check.SOURCE_DIRS` contains
      `tests`/`test` when those directories exist under the project root
- [ ] 1.5 Run the new test against the UNFIXED scripts and confirm it fails
      (red), so the test demonstrably detects the defect

## Sprint 2 — fix the gate

- [ ] 2.1 `scripts/regression_sizes.py::_classify_file`: replace the dead
      `"test_*.py"` glob literal with basename-based pytest matching
      (`test_` prefix + `.py` suffix); all other suffix matches unchanged
- [ ] 2.2 `scripts/regression_check.py`: add `tests` and `test` to the
      SOURCE_DIRS candidate list
- [ ] 2.3 Re-run `tests/test_regression_sizes.py` against the fixed scripts —
      green; full `pytest tests/` green; standalone mode green
- [ ] 2.4 `python3 scripts/regression_check.py --all` — exit 0, size report now
      enumerates the tests/ tree, no new breaches (all current test files
      are under TEST_HARD)

## Sprint 3 — close the failure record

- [ ] 3.1 Fill FAIL-f6228dda `fix_commit` with the implementation SHA and
      flip status to `resolved` (append-only style: in-place fill per repo
      precedent 6e5a939/d15628c)
- [ ] 3.2 Verify the registry check passes and the regression gate stays
      green on the closing commit
