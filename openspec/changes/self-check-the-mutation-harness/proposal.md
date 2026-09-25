# Proposal: self-check-the-mutation-harness

## Problem

Three mutation batteries live in `tests/` — `mutation_battery_size_scope.py`,
`mutation_battery_image_cycle.py`, `mutation_battery_image_state.py` — and each
carried a private copy of the machinery that decides a verdict: read the file,
assert the anchor appears exactly once, apply the edit, check the result still
parses, run the named test, read killed-or-survived off the exit status.

Two copies were byte-identical. The third, `_well_formed`, understood only
Python. It was correct for its own mutations by luck of what it happened to
mutate, not by rule: a battery that grew a `.sh` or a `.json` mutation would
have had its artifacts checked by a function that returns True for anything it
does not recognise.

The larger problem is what the copies had in common, which is that nothing
checked any of them. The batteries assert the property the whole ritual rests
on — that every guard is killable by exactly one named test, and that a negative
control survives — so the harness IS the evaluator. A harness that read a
mutant's SyntaxError as "a test caught it", or a stale anchor as a kill, would
turn every battery green while proving nothing, and no battery would notice
because every battery uses the same harness. `scripts/mutation_check.py` states
the rule for its own tool — "a mutation tool that silently misreports is itself
an evaluator integrity failure" — and guards it with `--self-check`. The
batteries had no equivalent.

Third: they are not `test_*.py`, so pytest does not collect them and no CI step
ran them. A survivor was visible only to whoever remembered to run a battery by
hand. `openspec/changes/add-runner-image-cycling/tasks.md` records that its
battery was first written in `/tmp` and "reproducible by nobody"; committing it
fixed half of that, and the other half — that nothing ran the committed copy —
stayed.

## Solution

- `tests/mutation_harness.py`: one harness, three batteries importing it.
  `well_formed` accepts all three artifact languages (`.py`, `.sh`, `.json`),
  because the batteries mutate all three.
- `tests/test_mutation_harness.py`: the self-check, in the collected lane rather
  than behind a flag, so it runs in CI for free. It drives the real harness
  against a synthetic repository whose outcomes are known by construction —
  a defect a named test catches, a change no test can see, an anchor that
  applies nowhere, a mutation that will not parse, a negative control that
  dies — and pins each verdict.
- A CI step running all three batteries, in the `evaluator-integrity` job,
  which already runs `mutation_check.py` and `negative_controls.py` for the same
  reason. Named individually, not globbed, so that
  `test_every_battery_runs_in_the_suite` can read the list back and fail when a
  battery exists that is not on it.

## What this does NOT fix

`scripts/mutation_check.py` — the repository's other mutation tool — is a
different implementation with its own self-check, and is not consolidated here.
It mutates a target with generated mutants rather than named edits, so the two
have different contracts and merging them would be a rewrite of a working
evaluator in the same change that starts measuring it.

`fw-ci-01..03`, named in `.github/workflows/ci.yml`, resolve to no requirement
in `openspec/specs/` — a tracing id with nothing behind it. Found while looking
for this package's spec home and left alone: it is a coverage defect in a
different capability, and quietly attaching this package's requirement to it
would hide the gap rather than close it.

## Affected specs

- `openspec/specs/gate-execution-contract/spec.md` — two ADDED requirements:
  that a harness which decides whether a test catches a defect is itself
  exercised against a known outcome, and that every battery is run by CI.
