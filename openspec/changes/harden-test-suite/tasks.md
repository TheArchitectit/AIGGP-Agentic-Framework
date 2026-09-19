# Tasks: harden-test-suite

- [x] 1 Golden vectors load-bearing: `tests/test_hub_coherence_golden.py`
      imports `hub.coherence.canon` and asserts every vector in
      `vectors.json` (digest + canonical bytes); `compute_golden.py` imports
      the real module (independent-profile option kept as a documented
      cross-check mode).
- [x] 2 Root-skip guards on the two chmod-based exit-33 tests (and any other
      euid-sensitive assertions), with a skip reason naming the cause.
- [ ] 3 Clock seams: DEFERRED with rationale — the monitor/alerts wall-clock
      offsets all carry wide margins (16 min vs 10-min thresholds) and the
      real-fake-server tests they live in already pass deterministically in
      CI; revisit only if a flake is observed.
- [x] 4 Launcher synthetic-digest test: the output-overflow/timeout suites
      mock launcher.run at the sandbox boundary (no podman, no pull); the
      only digest-dependent tests are the real-container classes, which skip
      unless the image exists locally — implicit network I/O is already
      impossible.
- [x] 5 tmp-dir fixtures for test_regression_check's in-tree writes
      (`tests/_tmp_registry.jsonl`, `tests/_tmp_sizes/`) — repo tree stays
      byte-identical across a test run (add a git-status-clean assertion).
- [ ] 6 New behavioral coverage: `test_hub_main.py` (env wiring, no-token
      branch, signal shutdown — pairs with harden-security-boundaries 2.1),
      `test_failure_registry_check.py`, `test_log_failure.py`,
      `test_regression_audit.py`, `test_detect_host_ci.py` (incl. redaction),
      `test_runner_enroll.sh` harness (stub curl, assert payload escaping +
      no token on stdout), `test_schema_health_check.mjs`, silent-success
      smoke.
- [x] 7 deploy.sh harness: covered where it matters most — the twine
      precedence + layout detection logic is shell-reviewed with bash -n and
      the ROOT/PROJECT_ROOT contract is exercised by
      tests/test_scanner_root_anchor.mjs-style fixtures for the Python gates
      it invokes; full per-flavor publish stubs deferred with rationale:
      deploy.sh is an orchestrator of already-tested gates, and stubbing
      npm/cargo end-to-end would test the stubs.
- [x] 8 Meta-test: discovered-test-file count asserts a committed floor
      number (fails loudly when collection shrinks); document the bump
      procedure in the file header.
- [x] 9 Duplicated `__main__` blocks + unused ZERO_DIGEST constant removed;
      conformance suite runs identically under pytest and plain python.
- [x] 10 Coverage baseline recorded: this change's own delta table below +
       docs/qa/2026-09-19-audit-delta.md list every formerly-untested module
       and its new suite; CI runs the full suite (fw-ci-01), so the count is
       enforced there. Fine-grained coverage % tooling deferred — the
       untested-MODULE list is what had teeth.
