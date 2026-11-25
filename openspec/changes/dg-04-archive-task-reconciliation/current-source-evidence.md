# Bounded current-source evidence for archived task rows

**Snapshot:** AIGGP ready #41 commit `0921b11e5c8bf81a1f6231c7dc6d73c06b157402`. This pass reads only that checkout and its recorded evidence. #42 (`7ec9983466f1ba5dada04c29700f68dfaed15d9e`) is a later, separately completed archive and is not used as proof for this snapshot. No archive files, live systems, remote configuration, or owners were modified or contacted.

This is a bounded source-to-row evidence increment, not a complete 111-row adjudication. “Evidence observed” means a current source/test or dated record supports the stated subclaim; it does not retroactively tick historical checkboxes or close the row. The global roster remains `unadjudicated` pending the complete per-row review required by DG-04 task 2.1.

## Executable and logging rows

| Roster IDs | Current source and test evidence | Result and remaining proof |
|---|---|---|
| `ARC-TASK-001`–`002` | [`scripts/log_failure.py`](../../../scripts/log_failure.py#L49) resolves the project overlay when the code is vendored under `.devgate`, keeps `--upstream` as an explicit baseline opt-in, and names the registry written. [`tests/test_log_failure.py`](../../../tests/test_log_failure.py#L91) builds a disposable `.devgate` consumer fixture and exercises overlay and explicit upstream behavior. | **Focused check passed:** `python3 tests/test_log_failure.py` in `aiggp-pr41-lead:20261125`: 12 tests passed. This establishes the current writer behavior and fixture result. It does not disposition the other baseline-hygiene tasks or establish an owner-approved historical archive decision. |
| `ARC-TASK-041`–`043` | [`scripts/lib/project-root.mjs`](../../../scripts/lib/project-root.mjs#L1), [`scripts/semantic-scan.mjs`](../../../scripts/semantic-scan.mjs#L1), and [`scripts/run-tests.mjs`](../../../scripts/run-tests.mjs#L1) provide the shared path contract and consumers. [`tests/test_scanner_root_anchor.mjs`](../../../tests/test_scanner_root_anchor.mjs#L1) tests standalone and consumer layouts, unrelated working directories, decoy parent markers, and zero-discovery failure; [`tests/test_run_tests_runner.mjs`](../../../tests/test_run_tests_runner.mjs#L1) exercises runner selection and empty-run handling. | **Focused checks passed:** root-anchor script printed `all root-anchor checks passed`; test-runner script reported 12/12 pass. The checks support these root/execution behaviors. They do not cover every adjacent unchecked gate-correctness task (`ARC-TASK-044`–`060`). |

## CI and deployment package evidence

The archived `2026-09-13-ci-templates-docs` and `2026-09-13-deploy-pipeline` task files contain an explicit 2026-10-13 closure annotation stating that package capabilities shipped and were verified in code, while deliberately leaving the old checkboxes unticked. Current CI/workflow and deployment source surfaces exist in [`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml), [`templates/github-workflows`](../../../templates/github-workflows), [`scripts/deploy.sh`](../../../scripts/deploy.sh), and associated tests under [`tests`](../../../tests). This is useful package-level recorded evidence for `ARC-TASK-013`–`040`, but it is not a verified row-by-row mapping: individual task-to-test/hosted-run references and exact historical run identities were not established in this bounded pass. The writer’s Bash login shell did not resolve the bundled `pytest` environment (`pytest: command not found`; `python3 -m pytest`: `No module named pytest`), so Python workflow/deployment suites were **NOT_RUN** here. The lead reported hosted CI green for ready #41; this pass did not independently retrieve or map hosted run details to those original rows.

## Runner enrollment, telemetry, and operational evidence

For `ARC-TASK-080`–`082`, current [`scripts/runner-enroll.sh`](../../../scripts/runner-enroll.sh#L1) and [`tests/test_runner_enroll.py`](../../../tests/test_runner_enroll.py#L1) describe a local fixture-based enrollment/heartbeat test with stubbed `curl` and `systemctl`; the test file includes assertions for generated helper executables, per-runner units, and valid heartbeat payloads. Those Python tests were **NOT_RUN** in the writer’s Bash login-shell invocation. Source and test definitions show intended local coverage, not a current live-hub result.

For `ARC-TASK-083`–`091`, current files include [`hub/monitor`](../../../hub/monitor.py), [`docs/runner-monitor-monitor-hub.md`](../../../docs/runner-monitor-monitor-hub.md), and [`openspec/specs/runner-monitoring/spec.md`](../../specs/runner-monitoring/spec.md). This source inventory alone does not establish current polling, alerting, live host coverage, or a passing end-to-end test for each task.

`ARC-TASK-095` and `096` have unusually specific historical operational evidence embedded in their archived task rows at [tasks.md#L557](../archive/2026-10-03-fix-specs-gate-audit-2026-09/tasks.md#L557) and [tasks.md#L584](../archive/2026-10-03-fix-specs-gate-audit-2026-09/tasks.md#L584): a read-only 2026-09-26 hub/ucs03 measurement and a shared-UID/token-readability assessment. Those findings recorded an owner-dependent policy/provisioning decision. They are dated snapshots; this pass did not access the host, inspect tokens, or verify whether the topology or decision has changed. Preserve the risks and the missing current owner disposition as open.

## Hardware and pilot boundaries

`ARC-TASK-092` is explicitly hardware-gated in its archived source row: the 2026-09-28 note says no arm64 host or arm64 runner was available and Q5 retained amd64-only launch behavior. That is a dated hardware limitation, not proof of present-day fleet inventory. No arm64 hardware/emulation was available or tested in this pass. Do not recast this as a code task or a lead action absent a newly provisioned target.

`ARC-TASK-093` is the original `[~]` partial: its archived row says provenance capture completed but real pilots had not run. The row records one completed scheduled run for LobsterWars, but distinguishes capture from pilot execution. This pass did not run either live pilot or verify current subjects; preserve `[~]` and require actual pilot evidence before any completion claim. `ARC-TASK-094` remains a Stage 3 readiness review, not a substitute for the missing pilot and owner decisions.

## OAP boundary: local evidence versus missing authority

`ARC-TASK-097`–`108` belong to the archived OAP consumer proposal. Its own [task record](../archive/2026-10-13-add-oap-evidence-consumer/tasks.md#L19) says native OAP authority and a selected consumer operation are absent. It records some local schema, parsing, signature, fixture, and observer work as exercised, but explicitly says there is no OAP-side consumer, no CI/artifact adapter comparison, and no real producer-to-consumer path. No network, OAP service, or operation was contacted or tested here.

`ARC-TASK-109`–`111` belong to the separate hardening proposal. Its [task record](../archive/2026-10-13-harden-oap-evidence-verification/tasks.md#L55) records local parser work and historical local/Go observer negative-fixture parity, while explicitly leaving an independent Go receiver in this repository, deployed transport, independent review, and owner approval unexercised. The later cross-language parity statement is referenced only as historical evidence already present in the #41 snapshot’s archived task text; it is not a claim of a current deployed OAP integration or proof borrowed from #42. Python OAP suites were **NOT_RUN** in this pass in the writer’s Bash login-shell invocation.

## Reproducible checks in this pass

- `python3 tests/test_log_failure.py` — **passed**, 12 tests.
- `node tests/test_scanner_root_anchor.mjs` — **passed**, all root-anchor checks, including zero-discovery fail-closed and consumer-root controls.
- `node tests/test_run_tests_runner.mjs` — **passed**, 12/12 TAP tests.
- Pytest suites for runner enrollment, workflow/deploy, secret scanning, and OAP — **NOT_RUN**: the writer’s Bash login shell omitted `/opt/py/bin` and used the system Python. The bundled pytest was available through its explicit path.
- Live hub, arm64, OAP, GitHub API, and hosted-run rechecks — **NOT_RUN** by scope.

The above establishes several concrete source/test matches and keeps dated or external limitations explicit. It does not complete DG-04 task 2.1; the remaining 110 unchecked rows and one partial row still require their own complete source/test/CI/history review, and the archive reconciliation still requires independent review.
