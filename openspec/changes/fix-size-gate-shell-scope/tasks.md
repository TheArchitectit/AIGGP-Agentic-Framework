# Tasks: fix-size-gate-shell-scope

Closes FAIL-8f9249ca (scope: the size gate did not size shell scripts) against
`scanner-parsing` gate-size-01 (MODIFIED) and gate-size-02 (ADDED).

## Sprint 1 — the RED, two fixtures the gate must flag

- [x] 1.1 `tests/test_regression_sizes.py`: `_write_sh_fixture` — a shell
      fixture that is really shell (shebang + `true # line N`), because a
      fixture claiming to be `.sh` should read as `.sh`
- [x] 1.2 MUST-flag: an `SRC_HARD + 1`-line `scripts/giant.sh` must be a
      blocking violation at SRC_HARD
- [x] 1.3 Classification: a 550-line `tests/test_big.sh` must NOT be flagged,
      and a `TEST_HARD + 1`-line `tests/test_giant.sh` must be flagged at
      TEST_HARD — and nothing else in that tree may be
- [x] 1.4 Red run against the unfixed gate: 2 failed (both new tests), 5 passed
      — the gate returned `[]` for every `.sh` file, which is the defect
      verbatim rather than a size disagreement

## Sprint 2 — the extension

- [x] 2.1 `SOURCE_EXTENSIONS` gains `.sh`. `.bash` was added first and removed:
      no file in the tree has that extension, and the ritual's rule is that a
      guard nothing exercises is decoration
- [x] 2.2 `TEST_PREFIX_EXTENSIONS = (".py", ".sh")`; `_classify_file` matches
      the prefix against that tuple. The convention is about naming, not about
      Python — without this, adding `.sh` would have introduced exactly the
      inconsistency the previous package removed for `.py`
- [x] 2.3 Green: `tests/test_regression_sizes.py` 7/7, with
      `tests/test_regression_check.py` 34/34

## Sprint 3 — what the extension newly reveals

- [x] 3.1 Measured `python3 scripts/regression_check.py --all` (read the report
      body, not the exit code — `--all` exits 0 while printing a blocking
      error): one hard breach, `scripts/runner-enroll.sh` (589 lines, limit
      500); two new soft warnings, `scripts/re-pin-evaluator-identity.sh`
      (407) and `scripts/deploy.sh` (377)
- [ ] 3.2 Split `runner-enroll.sh` at the unit-emission seam — see the record
      below
- [ ] 3.3 Re-measured after the split: 0 over hard limit, and the two new soft
      warnings stand (soft limits warn, they do not block; 11 pre-existing
      soft warnings were already there)

## Sprint 4 — the battery, and the gap it found

- [x] 4.1 `tests/mutation_battery_size_scope.py`: S1 (`.sh` dropped from
      `SOURCE_EXTENSIONS`), S2 (`.sh` dropped from `TEST_PREFIX_EXTENSIONS`),
      S3 (`scripts` dropped from the `SOURCE_DIRS` candidates), each naming the
      one test that kills it
- [x] 4.2 **S3 SURVIVED on the first run.** `scripts` in `SOURCE_DIRS` was
      asserted by nothing — `test_source_dirs_include_test_directories` pins
      `tests`/`test` only — so `.sh` in the extension list was load-bearing on
      a declaration no test depended on. Pinned with
      `test_source_dirs_include_the_directory_the_shell_scripts_live_in`, and
      the gap is why that test exists: it was found by mutation, not by a RED
      (it cannot have a RED — it asserts something already true)
- [x] 4.3 Re-run: 3/3 mutations killed, each by its named test (S2 by exactly
      one: `tests/test_giant.sh` is still flagged under S2 because 601 > 500
      as source, so only the `hard == TEST_HARD` assertion can see it)
- [x] 4.4 1/1 negative control behaved. N1 adds an extension nothing in the
      tree uses and MUST survive; it pins the battery's own kill detection,
      which is a different control from the sibling batteries' masking pairs —
      the reason is in the file's docstring rather than left implicit

## Sprint 5 — close the record

- [ ] 5.1 FAIL-8f9249ca entry appended to `.guardrails/failure-registry.jsonl`
      with the fix_commit filled in
- [ ] 5.2 `python3 scripts/failure_registry_check.py` clean;
      `npx openspec validate fix-size-gate-shell-scope --strict` valid;
      `--all --strict` unregressed
- [ ] 5.3 Local mirror: pytest, node suite, exec-bit guard, regression gate

## Record — why the split, and where

The gate's answer to an oversize file in this repository has been, three times
now, a structural fix rather than a limit change or a trim: the two oversize
test modules were split at real seams while closing Sprint 2.2, and the same
reasoning applies to a shell script. 589 lines against a 500-line limit is not
a miscalibrated limit — it is a script doing two jobs.

The seam is **unit emission vs the enrollment protocol**. What this script
decides (which runner, which hub, which token, which host may own a slug) is
not what a systemd user unit looks like. The emitted units are also the part
that grew: Sprint 2.2 added the cycle's service and timer to a file the checker
had never sized.
