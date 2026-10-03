# Tasks: self-check-the-mutation-harness

The batteries were not reproducible: three copies of the harness, and nothing
ran any of them. Closes that against `gate-execution-contract`
gate-selfcheck-01 and gate-battery-ci-01 (both ADDED).

## Sprint 1 — the guard for the harness, before the harness

- [x] 1.1 `tests/test_mutation_harness.py` written FIRST, against a harness that
      did not exist — the RED is `ModuleNotFoundError: No module named
      'mutation_harness'`, which is the weakest RED in this repository and is
      recorded as such: the file's value is not that it fails before the
      harness, it is that it fails after a harness that misreports
- [x] 1.2 Five verdicts pinned against a synthetic repository whose outcomes are
      known by construction: a defect a named test catches (killed), a change
      no test can see (survived), a survivor where a kill was expected (not
      True), an anchor that applies nowhere (None), a mutation that will not
      parse (INVALID, not a kill)
- [x] 1.3 Both `main` exit paths pinned: a survivor exits non-zero, and a
      negative control that dies exits non-zero
- [x] 1.4 The restore pinned in both directions — a killed mutation and an
      unapplied one must both leave the target file byte-identical, because the
      restore is what stops one run from judging the next

## Sprint 2 — one harness

- [x] 2.1 `tests/mutation_harness.py`: `well_formed` (`.py`/`.sh`/`.json`),
      `clear_bytecode`, `run_tests`, `run_entry`, `main`. The third battery's
      copy understood only Python and was right for its own mutations by luck
      of what it happened to mutate
- [x] 2.2 The three batteries rewritten onto it: 241→137, 194→104, 380→277
      lines. `run_entry` takes `root`, which is the injection seam the Sprint 1
      guards need; a root that is not the tree under test raises naming the file
      rather than reporting a verdict against nothing
- [x] 2.3 The batteries' verdicts are UNCHANGED, which is the only thing that
      makes the refactor a refactor: 3/3 + 1/1, 7/7 + 1/1, 34/34 + 1/1 — the
      same numbers as before, including the four anchors repointed when
      `runner-enroll.sh` was split
- [x] 2.4 `controls_note` is the caller's words: the size-scope battery's single
      control pins the harness's own kill detection, which is a different claim
      from the image batteries' masking pairs, and flattening both into one
      generic line would have made the difference unreadable

## Sprint 3 — the harness is itself mutated

- [x] 3.1 Three mutations of the harness, each killed by exactly one named test:
      `killed = res.returncode != 0` → `killed = True` (4 tests); the INVALID
      early return removed (1 test); the anchor-count check removed (1 test)
- [x] 3.2 Harness restored byte-identical after each (`cmp`) — a mutation
      battery for the harness that did not clean up would be worse than none

## Sprint 4 — reproducibility

- [x] 4.1 A CI step running all three batteries, in `evaluator-integrity` —
      the job that already runs `mutation_check.py --self-check` and
      `negative_controls.py` for the same reason
- [x] 4.2 Named individually rather than globbed, so
      `test_every_battery_runs_in_the_suite` can read the step back and fail
      when a battery exists that no step names. That test is what makes adding a
      fourth battery a decision rather than an oversight
- [x] 4.3 The step's own text is parsed, not merely searched: the test slices
      from `- name: mutation batteries` to the next step at the same indent, so
      a mention elsewhere in the file cannot satisfy it

## Sprint 5 — close the record

- [x] 5.1 `npx openspec validate self-check-the-mutation-harness --strict`
- [x] 5.2 `--all --strict` unregressed
- [x] 5.3 Local mirror: pytest, node suite, exec-bit guard, regression gate

## Record — what the consolidation found, and what it did not

**The third copy's `_well_formed` was Python-only.** `mutation_battery_size_scope.py`
mutated `scripts/regression_sizes.py` and checked `compile()`, which is correct
for every mutation it has. It would have been wrong for the first `.sh` or
`.json` mutation it grew, and nothing would have said so — the same shape as
the size gate's own defect, a scope declaration that is right today and silent
about the day it stops being.

**Nothing ran the batteries.** This is the finding that matters more than the
duplication. Committing them took them out of `/tmp` and made a survivor
re-checkable in principle; a step that runs them makes it re-checkable in fact.
`add-runner-image-cycling/tasks.md` item 6 records the first half and stops
there.

**`fw-ci-01..03` resolve to nothing.** Named in `.github/workflows/ci.yml`, in
no `openspec/specs/` file. Left alone deliberately: closing it means writing
requirements for a job that does not have them, which is its own change with its
own audit, and this package's requirements are about mutation batteries. Recorded
in the proposal so the gap is not mistaken for coverage.

**`scripts/mutation_check.py` is not consolidated.** It generates mutants from a
target rather than applying named edits, so it has a different contract and its
own `--self-check`. Merging the two would be rewriting a working evaluator in the
same change that begins measuring it.
