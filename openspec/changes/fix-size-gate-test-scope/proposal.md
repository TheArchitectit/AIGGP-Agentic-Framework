# Proposal: fix-size-gate-test-scope

## Problem

The file-size gate reported `0 over hard limit` while evaluating **no test
file at all** (failure registry: FAIL-f6228dda, category config, severity
medium). Two independent scope defects made the gate vacuously green for
every pytest file:

1. `scripts/regression_check.py` builds `SOURCE_DIRS` from a candidate list
   that includes `hub`, `scripts`, `openspec` — but not `tests` or `test`,
   so pytest trees were never walked.
2. `scripts/regression_sizes.py::_classify_file` lists `"test_*.py"` inside
   a `str.endswith(...)` tuple. That is a glob used as a literal suffix —
   `endswith("test_*.py")` can never match a real filename, so pytest-named
   test files silently got source limits (or were never scanned at all,
   because of defect 1).

Meanwhile `openspec/specs/scanner-parsing/` requirement `gate-size-01`
already mandates the intended behaviour: test files in `tests/` and `test/`
are discovered and evaluated against TEST_HARD (600), not SRC_HARD (500).
The implementation drifted from its own spec. A gate that scans nothing and
reports a clean pass is worse than no gate — it trains the reader to ignore
red.

## Solution

- Add `"tests"` and `"test"` to the `SOURCE_DIRS` candidate list in
  `scripts/regression_check.py`.
- Fix the matcher in `scripts/regression_sizes.py::_classify_file`: classify
  pytest files by basename (`test_*.py` prefix + `.py` suffix) instead of the
  dead glob literal, keeping the existing suffix-based matches unchanged.
- Add `tests/test_regression_sizes.py` — the self-test FAIL-f6228dda's
  prevention_rule demands: call `check_file_sizes`'s own API with
  known-oversize fixtures and assert it (a) flags a file it MUST flag, at
  TEST_HARD not SRC_HARD, (b) leaves a 550-line pytest file alone (the
  gate-size-01 scenario), and (c) really evaluates the fixture directory
  rather than reporting green on an empty scan.

No spec deltas: `gate-size-01` is already live and unchanged.

## Affected specs

- `openspec/specs/scanner-parsing/spec.md` (gate-size-01) — implementation
  brought into conformance; requirement text unchanged.
