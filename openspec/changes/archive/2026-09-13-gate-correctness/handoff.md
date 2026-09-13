# Handoff: gate-correctness

## Traceability

| Audit finding | Spec requirement | Sprint |
|---|---|---|
| C1 scene parse error | gate-tscn-01 | 4 |
| C2 semantic-scan crash | gate-root-01 | 1 |
| C3 vacuous run-tests | gate-root-01, gate-vacuous-01 | 1-2 |
| C4 cargo 0-test pass | gate-vacuous-01 | 2 |
| C5 --all vacuous arm | gate-allwindow-01 | 3 |
| H4 cfg(test) single-line | gate-rstest-01 | 4 |
| H5 test sizing | gate-size-01 | 5 |
| L1/L7 dead code | — | 6 |

## Executor notes

- Work item by item; each sprint ends green (44 existing tests + new fixtures).
- Fixture style: copy the scanner into a temp project like
  tests/test_guardrails_scan.mjs does — the scanners resolve root from their
  own file location, so fixtures must exec the copy.
- Do not touch pattern-rules.json or any rule data in this change.
- Verify before claiming done: run every touched gate against the audit's
  reproduction fixtures (all are in docs/qa/2026-09-13-full-qa.md).
