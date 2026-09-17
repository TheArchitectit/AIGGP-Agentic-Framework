# Known pre-existing gate defects (found during S2 audit)

Found by the independent auditor during S2 round 2, verified against the tree.
These are **pre-existing repo defects, not introduced by this change**, and they
are recorded here rather than silently fixed mid-sprint because changing gate
behavior affects every other change in flight.

## GD-1 — `_classify_file` test matcher is a glob used as a literal

`scripts/regression_sizes.py:62` lists `"test_*.py"` inside a tuple passed to
`str.endswith()`. `endswith` performs no globbing, and no filename literally ends
in the six characters `test_*.py`, so the test-file branch is **unreachable for
Python tests**. Verified:

```
$ python3 -c "import regression_sizes as rs; print(rs._classify_file('tests/test_hub_monitor.py'))"
(300, 500)          # expected (None, 600)
$ python3 -c "print('tests/test_hub_monitor.py'.endswith('test_*.py'))"
False
```

Effect: every `test_*.py` in the repo is measured against the *source* limits
(300 soft / 500 hard) instead of the test limit (600 hard). `_test.py` and the
`.test.ts`-style entries do work, so the bug is specific to the `test_*` prefix
form.

Suspected intent: the matcher should test the basename against a glob
(`fnmatch`) or check `name.startswith("test_")`.

## GD-2 — `tests/` is not in `SOURCE_DIRS`, so test files are never size-checked

`scripts/regression_check.py:97-105` builds `SOURCE_DIRS` from marker candidates
and resolves to `['scripts', 'openspec', 'hub']`. `tests` is absent, so
`check_file_sizes(PROJECT_ROOT, SOURCE_DIRS, ...)` returns `[]` regardless of how
large any test file becomes. Verified:

```
$ python3 -c "import regression_check as rc; print(rc.SOURCE_DIRS)"
['scripts', 'openspec', 'hub']
```

Effect: the gate reports "0 over hard limit" while an 894-line test file
(`tests/test_hub_coherence_conformance.py` at the time of the audit) sat well
over the 600 hard limit. **A gate that reports clean because it evaluated nothing
is a NOT_RUN reported as passed**, which `AGENTS.md` forbids.

Note the gate is honest in the other direction: with default `--staged` it prints
an explicit "NOTHING SCANNED — this run evaluated no inputs; it is NOT evidence of
a clean tree" banner. That self-reporting is the good pattern; GD-2 is the scope
gap it cannot detect on its own.

## Consequence for this change

- The S2 gate table must NOT cite `regression_check --all --pre-commit` as
  positive evidence that this change's test files are within budget. It is
  recorded as **PARTIAL: file-size rule did not evaluate the tests/ tree**.
- Action taken in this change: the oversized test file was split into
  `test_hub_coherence_conformance.py` (518), `test_hub_coherence_exitcodes.py`
  (138), and `test_hub_coherence_schema.py` (306). **`test_hub_coherence_conformance.py`
  at 518 lines is still over the 300 *soft* limit**, and under GD-1/GD-2 that is
  currently invisible to the gate. Splitting further is deferred to S3.
- Fixing GD-1/GD-2 changes gate behavior repo-wide and should be its own change
  with its own audit, not a drive-by during a feature sprint.

## Recommendation

Open a separate change for GD-1 + GD-2 together: fix the matcher, add `tests` to
`SOURCE_DIRS`, and expect a burst of newly-visible oversize test files across the
repo (which is exactly why it must not be bundled here).
