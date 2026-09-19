# Proposal: add-framework-ci-pipeline

## Problem

The 2026-09-13 QA (M9, verified) and the 2026-09-19 review confirm: **the
repository that ships CI-enforcement templates runs no CI on itself that
executes its test suite.** `.github/workflows/` contains only `drift-scan.yml`
(scanner gates on a schedule, self-hosted runner) and `hub-health-probe.yml`
(manual dispatch). Consequences verified live on 2026-09-19:

1. `pytest tests/` collection **silently drops the five core conformance files**
   on any machine with an installed `tests` package
   (`ModuleNotFoundError: No module named 'tests.fixtures.coherence'` —
   reproduced: 239 tests collect, 5 files error), because `tests/__init__.py`
   is missing and a regular package beats the namespace package regardless of
   path order. Nobody noticed because no CI runs the suite.
2. `tests/test_guardrails_scan.mjs` — the strongest scanner-semantics suite —
   is executed by nothing (not matched by `run-tests.mjs` discovery, not run
   by any workflow).
3. `openspec validate` failures (15/15 main specs fail CLI validation — see
   the migration change) are invisible.
4. The gold-standard practice the repo preaches (gates at the HEAD you push)
   is not applied to the framework itself: PRs can merge with zero checks.

## Solution

Add `.github/workflows/ci.yml` (and extend the drift-scan job) to run on PRs
and pushes to main:

1. **Test job** (ubuntu runner): `python3 -m pytest tests/ -v` with
   `tests/__init__.py` added (this change) so collection is deterministic;
   `node --test tests/test_guardrails_scan.mjs`; report counts in the step
   summary; job fails on any failure.
2. **OpenSpec job**: `openspec validate --all --strict` once the migration
   change lands (until then, run `python3 scripts/spec_traceability.py` in
   blocking mode for the framework's own capabilities, which is the
   repo's current enforced equivalent).
3. **Self-gate job**: run the framework's own gates against its own tree
   (`guardrails-scan`, `semantic-scan`, `regression_check --base origin/main`,
   `silent-success-scan`, `failure_registry_check`) — the framework must be
   warning-clean on itself (QA L3: PREVENT-024 currently fires on a test file).
4. **Container job** (optional/follow-up, can be folded in after the
   container-contract fix): build the pinned image, run the in-container
   valid-request smoke case.
5. Pin every action by commit SHA (the live drift-scan.yml already pins
   `actions/checkout` by SHA but uses a mutable `actions/setup-node@v4` in the
   same file).

This change also adds `tests/__init__.py` and `tests/conftest.py` (repo-root
`sys.path` insertion so `python3 -m pytest` works from any CWD) — the minimum
test-infra fix the CI job depends on. Deeper suite hardening is scoped to the
`harden-test-suite` change.

## Impact

- New `.github/workflows/ci.yml`; edit `drift-scan.yml` (SHA-pin setup-node).
- `tests/__init__.py`, `tests/conftest.py` added.
- README "CI Integration" section gains a note that the framework runs its own
  medicine on itself (doc-truth).
- Spec delta: new capability `framework-ci` defining what the repo's own CI
  must enforce (tests executed, gates self-applied, spec validation present).
