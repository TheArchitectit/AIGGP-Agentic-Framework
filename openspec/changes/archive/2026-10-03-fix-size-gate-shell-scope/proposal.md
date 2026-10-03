# Proposal: fix-size-gate-shell-scope

## Problem

The file-size gate sized sixteen languages and not the one this repository's
fleet-side scripts are written in. `SOURCE_EXTENSIONS` in
`scripts/regression_sizes.py` listed `.ts` through `.cs` and no `.sh`, so
`scripts/` was walked and every shell script inside it was skipped. Measured
on this tree at HEAD before the fix (failure registry: FAIL-8f9249ca,
category config, severity medium):

```
  ERROR  scripts/runner-enroll.sh  (589 lines, limit 500)  OVER HARD LIMIT
```

That line did not exist before. `runner-enroll.sh` — the script that writes a
host's systemd units, holds its heartbeat token to a 0600 file, and is the
subject of two incident records (FAIL-6e7b6f84, FAIL-ac75444c) — passed 589
lines against a 500-line limit with the gate reporting nothing, and it grew
past the limit while the gate was blind: Sprint 2.2 added the image-cycle units
to a script the checker had never sized.

This is the same shape as FAIL-f6228dda, and the previous change package
(`fix-size-gate-test-scope`) fixed the matcher half of it. The SCOPE half
recurred with a different declaration: then it was `SOURCE_DIRS` missing
`tests`, now it is `SOURCE_EXTENSIONS` missing the language the scripts are
written in. A gate whose scope is a hand-maintained list drifts from its intent
silently, and reports green while looking at nothing.

## Solution

- Add `.sh` to `SOURCE_EXTENSIONS` in `scripts/regression_sizes.py`. `.bash` is
  deliberately NOT added: no file in the tree has that extension, and an
  untested scope entry is a claim nobody checks.
- Extend the `test_*` prefix convention to shell files
  (`TEST_PREFIX_EXTENSIONS = (".py", ".sh")`). The convention is about naming,
  not about Python; without this, `tests/test_x.sh` at 550 lines would be
  judged at SRC_HARD while its Python sibling got TEST_HARD.
- Add three MUST-flag tests to `tests/test_regression_sizes.py`: an oversize
  `.sh` file at SRC_HARD, a shell test classified at TEST_HARD, and — found by
  the battery rather than by a RED — that `scripts/` is in `SOURCE_DIRS` at
  all, which is what makes the extension load-bearing.
- Add `tests/mutation_battery_size_scope.py`: 3/3 mutations killed, 1/1
  negative control behaved.

## What this reveals and does NOT yet fix

The gate now reports one blocking breach it could not see before —
`scripts/runner-enroll.sh` at 589 lines — and two new soft-limit warnings
(`scripts/re-pin-evaluator-identity.sh` 407, `scripts/deploy.sh` 377). The
blocking one is a structural finding and the next commit in this task splits
the script at its seam (unit emission vs enrollment protocol) rather than
raising a limit or trimming code, exactly as the two oversize test modules were
split rather than trimmed earlier in this session while closing Sprint 2.2.
Until that lands, a diff that touches `runner-enroll.sh` blocks on this limit —
which is the gate working, not a regression.

## Affected specs

- `openspec/specs/scanner-parsing/spec.md` — `gate-size-01` MODIFIED (the test
  naming list gains the shell convention) and `gate-size-02` ADDED (shell
  script sizing and the script directory being in scope).
