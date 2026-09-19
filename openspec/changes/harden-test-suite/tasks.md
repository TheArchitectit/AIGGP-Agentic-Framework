# Tasks: harden-test-suite

- [ ] 1 Golden vectors load-bearing: `tests/test_hub_coherence_golden.py`
      imports `hub.coherence.canon` and asserts every vector in
      `vectors.json` (digest + canonical bytes); `compute_golden.py` imports
      the real module (independent-profile option kept as a documented
      cross-check mode).
- [ ] 2 Root-skip guards on the two chmod-based exit-33 tests (and any other
      euid-sensitive assertions), with a skip reason naming the cause.
- [ ] 3 Clock seams: `MonitorLoop`/`GitHubIssueNotifier` accept an injectable
      `now`; the wall-clock-offset tests converted to frozen reference times
      (pattern already proven in test_hub_coherence_report.py:11).
- [ ] 4 Launcher synthetic-digest test: gate on locally-built image (like the
      container smoke) or re-point at a digest that cannot trigger a pull;
      no test performs implicit network I/O.
- [ ] 5 tmp-dir fixtures for test_regression_check's in-tree writes
      (`tests/_tmp_registry.jsonl`, `tests/_tmp_sizes/`) — repo tree stays
      byte-identical across a test run (add a git-status-clean assertion).
- [ ] 6 New behavioral coverage: `test_hub_main.py` (env wiring, no-token
      branch, signal shutdown — pairs with harden-security-boundaries 2.1),
      `test_failure_registry_check.py`, `test_log_failure.py`,
      `test_regression_audit.py`, `test_detect_host_ci.py` (incl. redaction),
      `test_runner_enroll.sh` harness (stub curl, assert payload escaping +
      no token on stdout), `test_schema_health_check.mjs`, silent-success
      smoke.
- [ ] 7 deploy.sh harness: fixture project per package-manager flavor in tmp
      (npm, cargo, pyproject; go/godot skip branches), asserting gate
      ordering and the fixed twine precedence (dry-run publish stub).
- [ ] 8 Meta-test: discovered-test-file count asserts a committed floor
      number (fails loudly when collection shrinks); document the bump
      procedure in the file header.
- [ ] 9 Duplicated `__main__` blocks + unused ZERO_DIGEST constant removed;
      conformance suite runs identically under pytest and plain python.
- [ ] 10 Coverage report step (CI): baseline numbers recorded in
       docs/qa; untested-module list from the proposal driven to zero or
       each remainder recorded with rationale.
