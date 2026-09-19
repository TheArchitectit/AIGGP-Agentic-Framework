# Proposal: fix-vacuous-and-broken-gates

## Problem

The 2026-09-13 external QA (`docs/qa/2026-09-13-full-qa.md`) verified seven
critical/high gate defects. A 2026-09-19 full review re-verified each against
current HEAD: **six of seven are still open**, and they are the exact
"silent-success / wrong-tree" failure classes this framework exists to prevent.

1. **C1 (open)** `scripts/scene_inventory.py:44-47` — `ET.parse()` runs before
   the regex parser; `.tscn` is not XML, so every valid Godot scene fails with
   `parse error` (exit 1). The gate cannot pass on valid input, and its regex
   path (which compares node-path connections against bare button names) is
   unreachable.
2. **C2/C3 (open)** `scripts/semantic-scan.mjs:23-36` and
   `scripts/run-tests.mjs:28-41` — both `findProjectRoot()` walks return the
   walk's start directory when no marker is found. On a standalone checkout
   that start is the repo's *parent*: semantic-scan crashes on `EACCES` or
   scans sibling repos; run-tests reports `0 passed, 0 failed across 0 files`
   with exit 0 while the repo's own tests sit unrun. `guardrails-scan.mjs:23`
   fixed this exact bug (`.devgate` basename check) — the fix was never
   ported.
3. **C4 (open)** `scripts/run-tests.mjs:90-97` — the Rust arm runs
   `cargo test -- <stem>`; the positional argument filters *test function
   names*, so an integration test file whose functions don't contain the stem
   runs zero tests and the file reports ✓.
4. **C6 (open)** `scripts/regression_audit.py:64` — `is_runtime` keys on npm's
   `effects` list, which enumerates *dependents* and is `[]` for direct
   dependencies. A HIGH vulnerability in a direct runtime dependency
   (verified live with `lodash@4.17.15`) classifies as dev-only and never
   blocks.
5. **C7 (open)** `scripts/deploy.sh:48,70` + `scripts/regression_check.py:83-94`
   — deploy cds into the DevGate tree and runs `regression_check.py --all`;
   `find_project_root()` walks from CWD and stops at the first `.git`, which in
   a submodule layout is the submodule itself. The release gate audits DevGate,
   not the project being published. The adjacent guardrails-scan anchors on
   script location and targets the project — the two deploy gates evaluate
   different repositories.
6. **H7 (open)** `scripts/deploy.sh:349` —
   `twine upload dist/* 2>/dev/null || python3 -m build && twine upload dist/*`
   parses as `(A || B) && C`: when the first upload succeeds, the `&& C` leg
   re-uploads; twine rejects the duplicate and `set -e` aborts the pipeline
   *after* the immutable publish. `2>/dev/null` also hides the real error.
7. **H6 (open)** `scripts/spec_traceability.py:23` — the marker grammar is
   `//`-only while `SCAN_EXTS` includes `.py`; `# spec: <id>` never matches, so
   a Python consumer in blocking mode is pinned at 0% coverage forever. The
   scaffolder's own advice (`scripts/findings_to_spec.py:137`) tells
   implementers to use the syntax Python doesn't have.
8. **H8 (open)** `scripts/log_failure.py:46-47` — `DEFAULT_REGISTRY` points
   inside the DevGate submodule. A consumer following AGENTS.md appends *their*
   bug to the *shared* baseline — the documented mechanism by which the shipped
   registry accumulated 12+ entries referencing other repos' files.
9. **New (not in prior QA)** `scripts/failure_registry_check.py:134-154` — an
   explicit `FAILURE_REGISTRY_PATH` that does not exist is silently skipped for
   the non-`devgate` label; a typo'd env var yields zero entries, zero errors,
   exit 0 — a vacuous green from the hygiene gate itself.
10. **New** `scripts/run-tests.mjs:51-61` — `isTestFile` matches `*.test.mjs`
    but the repo's strongest scanner test is named `test_guardrails_scan.mjs`
    (`test_*.mjs`): matched by neither the runner's discovery nor any CI, it is
    silently absent from every automated run.

These are not enhancements; they are the framework's flagship failure modes
firing in its own shipped gates.

## Solution

Port the proven `guardrails-scan.mjs` root-anchoring contract to
`semantic-scan.mjs` and `run-tests.mjs` (standalone DevGate is its own
project). Fix the cargo invocation (`--test <stem>`), the npm runtime
classification (`isDirect`/`name in runtime_deps`, not `effects`), the deploy
gate's working tree (anchor on the detected project root, not the submodule),
the twine upload precedence (explicit `if ! A; then B && C; fi` with visible
stderr, upload only the just-built version's artifacts), the marker grammar
(accept `#` comment prefixes for `.py`/`.rb`/`.sh`, emit correct per-language
advice), the default registry target (project overlay with explicit
`--baseline` opt-in for upstream), and the hygiene gate's explicit-path
handling (a named path that does not exist is exit 1, never skip). Make
`run-tests.mjs` discovery cover `test_*.mjs` and the documented "anywhere in
your project" claim, and either repair `scene_inventory.py` (drop the
`ET.parse` dead-end, fix the node-path comparison, add a self-test) or remove
the gate and its spec references — a gate that fails 100% of valid input is
worse than no gate.

## Impact

- `scripts/`: scene_inventory.py, semantic-scan.mjs, run-tests.mjs,
  regression_audit.py, regression_check.py, deploy.sh, spec_traceability.py,
  findings_to_spec.py, log_failure.py, failure_registry_check.py
- `tests/`: new regression tests for each fix (root anchoring, cargo filter,
  npm classification, marker grammar, registry target, vacuous-path)
- No spec deltas: `gate-execution-contract`, `scanner-parsing`,
  `rule-coverage-truth`, and `doc-truth` already mandate this behavior — this
  change brings the implementation into conformance with live requirements
  (same pattern as `fix-size-gate-test-scope`).
