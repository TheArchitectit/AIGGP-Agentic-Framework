# Tasks: add-framework-ci-pipeline

## 1. Test-infra prerequisites

- [x] 1.1 Add empty `tests/__init__.py` (kills the namespace-package shadowing
       that silently drops the five conformance files).
- [x] 1.2 Add `tests/conftest.py` inserting the repo root on `sys.path`.
- [x] 1.3 Verify: `python3 -m pytest tests/` collects and runs all test files
       on a clean environment AND on one with a foreign `tests` package
       installed (the reproduction case from the proposal).

## 2. Workflow

- [x] 2.1 `.github/workflows/ci.yml`: trigger on PR + push to main.
- [x] 2.2 Job `tests`: checkout (SHA-pinned), setup-python 3.12, `pytest
       tests/ -v`; `node --test tests/test_guardrails_scan.mjs`; publish
       pass/fail counts to the step summary; fail on nonzero.
- [x] 2.3 Job `self-gates`: run `guardrails-scan.mjs`, `semantic-scan.mjs`
       (typescript installed), `regression_check.py --base origin/main
       --fail-if-empty`, `silent-success-scan.sh`,
       `failure_registry_check.py`; fix the PREVENT-024 self-hit
       (tests/test_regression_check.py:45) so the tree is warning-clean.
- [x] 2.4 Job `specs`: traceability runs with visible counts; **blocking is
       deferred** — coverage is 57/112 today (measured), so declaring it
       blocking would fail every run. `openspec validate` runs informational
       until `migrate-specs-to-openspec-conventions` makes the tree CLI-valid
       and flips both to hard gates.
- [x] 2.5 SHA-pin every action used (`actions/checkout`, `actions/setup-node`,
       `actions/setup-python`); no mutable tags in the repo's own workflows.
- [x] 2.6 Runner targeting consistent with the fleet standard (`runs-on:
       devgate` or hosted fallback documented in the workflow header).

## 3. Container smoke (after fix-coherence-container-contract)

- [x] 3.1 Job `container` (allow-failure rollout or hard, decide in review):
       build the image, run the in-container valid-request PASS case and the
       honest-rejection case from the updated smoke tests.
- [x] 3.2 Record in the job summary the built manifest digest and confirm it
       matches `container/execution-profiles.json` (or opens a follow-up task
       when it legitimately drifts after a rebuild).

## 4. Docs

- [x] 4.1 README CI section: state that the framework CI-runs its own suite
       and gates (with the workflow filename).
- [x] 4.2 AGENTS.md: before-you-push checklist includes watching the repo's
       own CI, not just local gates.
- [x] 4.3 docs/qa note: M9 closed.
