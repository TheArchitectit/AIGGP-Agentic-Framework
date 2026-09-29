# Tasks: fix-size-gate-test-scope

Conformance fix for FAIL-f6228dda against `scanner-parsing` gate-size-01
(no spec deltas — implementation only, `skip_specs: true`).

## Sprint 1 — self-test first (prevention_rule: feed the gate a file it MUST flag)

- [x] 1.1 `tests/test_regression_sizes.py`: known-oversize pytest fixture
      (`tests/test_giant.py`, TEST_HARD+1 lines) through `check_file_sizes`'
      own API — must be flagged with `hard == TEST_HARD` (600), proving test
      classification and that the fixture directory is really evaluated
- [x] 1.2 Same file: the gate-size-01 scenario — a 550-line pytest file must
      NOT be flagged (TEST_HARD 600, not SRC_HARD 500)
- [x] 1.3 Matcher contrast: a non-test `.py` file at SRC_HARD+1 lines must be
      flagged at `hard == SRC_HARD` while the same-size `test_*.py` file is not
- [x] 1.4 Scope-list assertion: `regression_check.SOURCE_DIRS` contains
      `tests`/`test` when those directories exist under the project root
- [x] 1.5 Red run against the UNFIXED scripts: 4/5 failed, reproducing the
      defect verbatim — `SOURCE_DIRS` was `['scripts', 'openspec', 'hub']`
      (no tests), `tests/test_501.py` evaluated at `hard=500`, the 550-line
      fixture flagged as a blocking error

## Sprint 2 — fix the gate

- [x] 2.1 `scripts/regression_sizes.py::_classify_file`: replace the dead
      `"test_*.py"` glob literal with basename-based pytest matching
      (`test_` prefix + `.py` suffix); all other suffix matches unchanged
- [x] 2.2 `scripts/regression_check.py`: add `tests` and `test` to the
      SOURCE_DIRS candidate list
- [x] 2.3 Green: standalone 5/5; `pytest tests/` 269 passed (includes the 5
      new tests); `--staged --pre-commit` exit 0
- [x] 2.4 `python3 scripts/regression_check.py --all` — exit 0, size report
      now walks the tests/ tree, 0 over hard limit, no new breaches (2
      pre-existing soft-limit warnings unchanged: regression_check.py,
      hub/monitor.py)

## Sprint 3 — close the failure record

- [x] 3.1 FAIL-f6228dda `fix_commit` filled with
      `7e559ba5dc51a4e58726161900a592ac72dbfabd`, status `resolved`
      (in-place fill per repo precedent 6e5a939/d15628c)
- [x] 3.2 Registry check + `--staged --pre-commit` green on this closing
      commit's staged content; `openspec validate fix-size-gate-test-scope
      --strict` valid
