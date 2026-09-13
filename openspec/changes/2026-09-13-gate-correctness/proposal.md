# Proposal: Repair gate correctness — scanners that crash, vacuously pass, or mis-parse

**Change ID:** 2026-09-13-gate-correctness
**Source audit:** docs/qa/2026-09-13-full-qa.md (findings C1-C5, H4, H5, L1, L7)
**Status:** Proposed

## Problem

Five of DevGate's shipped gates fail in the exact layouts they are sold for,
in both directions — failing closed on valid input and passing green over
unscanned work:

1. **scene_inventory.py fails every valid Godot scene** (C1): `ET.parse()`
   rejects `.tscn` before the regex parser is reached; gate exits 1 on any
   real project. [verified]
2. **semantic-scan.mjs crashes on standalone checkouts** (C2): the walk-up
   project-root detection escapes the repo and scans its parent; reproduced
   as `EACCES … scandir '/tmp/…'`, exit 1. [verified]
3. **run-tests.mjs passes green running zero tests** (C3): same root escape
   yields `TOTAL: 0 passed, 0 failed across 0 files`, exit 0, while the repo's
   own 6 test files sit unrun; discovery is also hardcoded to
   `dist|test|tests|src` despite the documented "anywhere in your project".
   [verified]
4. **run-tests.mjs Rust arm runs 0 tests and passes** (C4): `cargo test --
   <file-stem>` filters by test *function* name, not file stem; every Rust
   integration test file reports ✓ while running nothing. [code-read]
5. **regression_check.py --all pattern arm is vacuous in clean CI** (C5): the
   pattern-rule arm scans the (empty) working-tree diff while the registry
   arm scans `tag...HEAD`; the drift-scan template and README claim a
   full-tree sweep. A committed critical PREVENT-007 violation was invisible
   to `--all --pre-commit`. [verified]
6. **Rust #[cfg(test)] blanking breaks on the single-line module form** (H4):
   `#[cfg(test)] mod tests {` leaves test lines scanned as production;
   reproduced as a critical PREVENT-003 false positive, exit 1. [verified]
7. **Pytest test files escape the file-size gate twice** (H5): `tests/` is not
   in SOURCE_DIRS, and the `"test_*.py"` literal inside `endswith()` never
   matches, so TEST_HARD=600 is dead configuration. [verified]

Each of these is the failure class the framework exists to catch — a gate
that reports green without doing the work, or a gate nobody can keep enabled
because it fails on valid input.

## Scope

Fix the seven defects above in place, add fixture-level regression tests for
each (the test suite currently never executes the broken paths), and align
the documented contract (`--all` semantics, test discovery roots, scene
parsing) with what the gates actually do. No new gates, no rule changes, no
consumer-facing layout changes.

## Non-goals

- Implementing the nine unenforced semantic rules (separate change:
  2026-09-13-rule-enforcement-gaps).
- CI template changes (separate change: 2026-09-13-ci-templates-docs) —
  though C5's fix must keep the drift-scan contract coherent.
- npm audit / deploy pipeline defects (separate change:
  2026-09-13-deploy-pipeline).

## Success criteria

- Every defect above has a fixture test that fails before the fix and passes
  after, in the style of tests/test_guardrails_scan.mjs.
- `node scripts/semantic-scan.mjs` and `node scripts/run-tests.mjs` exit 0
  *after doing their work* on a standalone DevGate checkout.
- `scene_inventory.py` accepts the minimal valid scene from the audit and
  still fails genuinely orphaned buttons.
- `--all` pattern findings equal the registry arm's diff window
  (`tag...HEAD`), and the docs say what it does.
