# DG-21 — process launch failure handling

**Reviewed baseline:** `2bf84ddab55695340e91ceb026b319fcae7de3e4`
**Scope status:** runner launch-error fix and focused behavior checks are complete. The CI completion-receipt work and broader gates remain open.

## CI evidence

- Main job [139576313889](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/45720189050/job/139576313889) ran Node `v20.20.2` on `ucs03-devgate-spare1`. In the per-file runner step, after launching eight files at pool size 8, Node raised an unhandled `Error: spawn python3 EAGAIN` (`errno: -11`) for `fleet-manager/tests/test_channel_v1.py`; the job exited 1 before the runner could report its remaining queue or start solo adjudication.
- Retry job [139585805765](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/45720189050/job/139585805765) completed its first runner invocation with `TOTAL: 2569 passed, 0 failed across 173 files in 82.0s`. The separate non-vacuity step invoked `node scripts/run-tests.mjs` a second time and failed with the same unhandled `spawn python3 EAGAIN` (`errno: -11`). This establishes that the duplicate runner invocation could independently hit the same launch failure.

## Local reproduction and runner results

- Baseline red: `node --test --test-name-pattern='accounts for a missing Python executable' tests/test_run_tests_runner.mjs` exited 1 on Node `v24.22.3`. Its real-runner fixture removed `python3` from `PATH`; the runner emitted an unhandled `spawn python3 ENOENT` and terminated before the later healthy sibling ran.
- After the fix: `node --test --test-name-pattern='missing Python executable|persistent EAGAIN|clears EAGAIN|zero tests' tests/test_run_tests_runner.mjs` passed all four focused behavior tests. They exercise the real `run-tests.mjs` process, a real missing executable, a deterministic preload-injected EAGAIN, a healthy sibling, persistent failure, a successful solo retry, and rejection of a zero-test solo retry.
- The complete file command `node --test tests/test_run_tests_runner.mjs` ran 16 tests: 14 passed and 2 failed. Both failures are the existing shell-script Vitest stub fixtures (`run-tests delegates to the stub vitest...` and `run-tests fails a 1..0 stub run...`), because Windows cannot execute the fixture's POSIX `node_modules/.bin/vitest` file (`ENOENT`). No claim is made that the complete file suite passed on this Windows host.
- Pinned OpenSpec CLI `1.14.3`: `openspec validate dg21-handle-test-process-launch-failures --strict` passed after the change artifacts were added.
- `.guardrails/failure-registry.jsonl` was appended through `scripts/log_failure.py`; generated ID: `FAIL-97423e98`.
- `CHECKSUMS.sha256` was updated only for `scripts/run-tests.mjs`. Its canonical-LF SHA-256 is `a8801827950f46770022f8070d45c487ed768b3081c37a50155c45587fd85b18`; verify that entry against the generated script bytes before promotion.

## Implementation boundary

`scripts/run-tests.mjs` now consumes ChildProcess `error` events, retains the launch diagnostic in the per-file result and final failure list, and settles each file once through timer and scratch-directory cleanup. The existing solo adjudication remains the only recovery path and still rejects a zero-test run. No pool, timeout, engine-selection, or test success criteria were changed.

The CI receipt change described by the active design is not implemented in this increment. Tasks 2.3, 2.4, and 3.1 remain open; no version or release reference, commit, archive, or remote write was made.

## Linux Docker verification

Docker verified code commit `1a3d0a503a9a7e2da9af7945576fff6ee1036a6c`. All 19 Node runner and workflow tests passed, including exactly one invocation, a successful positive report, missing/malformed/zero counts, and a failed runner that printed a positive count. Failure-registry hygiene, verification of all 160 tracked checksums, the scoped regression gate, and strict OpenSpec validation of 76 items passed. The registry points to the commit that implemented per-file launch handling. The updated GitHub checks will run on the pushed candidate.
