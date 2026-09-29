# Proposal: harden-test-suite

## Problem

The 2026-09-19 test review graded the suite by the repo's own rubric
(behavioral / contract / presence). Verdict: the coherence suite is genuinely
strong (~85% behavioral, mocks only at true boundaries, mutation rationale in
docstrings) — but the infrastructure around it silently loses tests, and
several modules ship untested:

1. **Collection loss (reproduced):** missing `tests/__init__.py` lets any
   environment with an installed `tests` package shadow the repo's namespace
   package — the five conformance files (`conformance`, `exitcodes`, `issue`,
   `ladder`, `schema`) error with `ModuleNotFoundError` while 239 other tests
   still pass. Addressed minimally in add-framework-ci-pipeline; this change
   owns the broader hardening.
2. **Never-run suites:** `tests/test_guardrails_scan.mjs` matched by no
   runner (see fix-vacuous-and-broken-gates 2.3); no CI at all today.
3. **Dead golden vectors:** `tests/fixtures/coherence/vectors.json`,
   `hello_lf/crlf.txt`, `canonical_sample.json` are consumed by nothing;
   `compute_golden.py` re-implements `canon` locally instead of importing
   `hub.coherence.canon` — the compatibility contract `coh-id-01` names is
   asserted nowhere, so a serialization change would pass green.
4. **Untested modules:** `hub/main.py` (entrypoint, signal shutdown, no-token
   branch); scripts `detect-host-ci.py`, `failure_registry_check.py`,
   `log_failure.py`, `regression_audit.py`, `scene_inventory.py`,
   `runner-enroll.sh`, `silent-success-scan.sh`, `schema-health-check.mjs`,
   `deploy.sh`.
5. **Environment sensitivities:** unwritable-dir exit-33 tests
   (`test_hub_coherence_exitcodes.py:98,146`) silently invert when run as
   root (no `skipIf(geteuid()==0)`); monitor/alerts tests use wall-clock
   offsets where the coherence suite freezes time; one launcher test uses a
   synthetic digest its own setUp warns triggers a registry pull.
6. **Tree pollution:** `test_regression_check.py:231,361-367` writes fixtures
   inside the repo's `tests/` dir (self-trips the size/regression scanners
   mid-run) instead of tmp.

## Solution

Treat the test suite as a gated artifact: deterministic collection (init +
conftest; already partially in the CI change — here: root-skip guards, frozen
clocks, tmp-dir fixtures), the golden vectors made load-bearing (a test
imports `hub.coherence.canon` and asserts the frozen vectors; the generator
switched to importing the real module so regeneration exercises the real
path — its independence becomes the cross-check), coverage for every untested
module at contract-or-better grade (deploy.sh and runner-enroll.sh get
fixture-project harnesses in tmp dirs; failure_registry_check and
log_failure get behavioral tests over temp registries; detect-host-ci gets
fixture workflow trees incl. redaction assertions; regression_audit gets the
npm fixture documents), and the flake sources removed (frozen reference times
via injectable clock, root-skip decorators, synthetic-digest test re-pointed
at the locally built image or skipped-with-reason). Add a meta-test that
counts discovered test files and fails when the count drops (the "silently
smaller suite" guard fw-ci-01 names).

## Impact

- `tests/` (new files + targeted edits), `tests/fixtures/coherence/
  compute_golden.py` (import real canon), no production code changes except
  optional clock-injection seams in `hub/monitor.py` / `hub/alerts.py`
  (constructor-injected `now` function, defaulting to real clock —
  behavior-preserving).
- No spec deltas: gate-execution-contract and the CI capability's fw-ci-01
  already demand honest execution; this change is conformance (skip_specs).
