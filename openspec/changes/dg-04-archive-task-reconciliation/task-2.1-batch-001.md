# DG-04 bounded task evidence batch 001

**Reviewed snapshot:** AIGGP main at `96632e91ad605970014d900686ae6f62e2762065`. Source review and behavioral tests used a disposable Linux checkout of that commit.

## Scope and disposition

This is the first source-line-ordered batch of the 111 stable roster entries: `ARC-TASK-001` and `ARC-TASK-002`, both from the 2026-09-13 baseline-hygiene archive. The rows map to archived tasks `1.1` and `1.2` (tasks.md lines 10–13). Their original `[ ]` boxes and source text remain unchanged.

| Stable ID | Historical task | Evidence reviewed at current main | Batch finding |
|---|---|---|---|
| `ARC-TASK-001` | `1.1 log_failure.py: project-overlay default in submodule layout + --upstream flag + written-path output` | The current [`log_failure.py`](../../../scripts/log_failure.py#L67) defaults to the project overlay, accepts `--upstream` (line 209), and prints the resolved registry path (line 259). [`TestBaseWrite01Contract`](../../../tests/test_log_failure.py#L92) exercises default overlay selection and explicit baseline selection, asserting the actual path and exclusivity. The current canonical [`base-write-01`](../../specs/baseline-ownership/spec.md#L32) requires those behaviors. | **Implemented.** Supported by current source and behavior tests. |
| `ARC-TASK-002` | `1.2 Fixture: submodule layout appends to project overlay; --upstream writes baseline` | The test fixture stages the actual script in a temporary `.devgate/scripts` tree and runs it as a consumer. `test_default_writes_the_project_overlay_and_names_it` and `test_upstream_writes_the_shared_baseline_and_names_it` assert file placement, output path, and that the alternate destination is absent. The historical fix commit `140deb8e763f02dc27e811fdf2b48c9854da3fea` changed both implementation and these behavioral fixtures, and is an ancestor of the reviewed main commit. | **Implemented.** Supported by the current consumer-layout fixture. |

The archived package carries a 2026-10-13 note that its capabilities shipped, but this batch independently checked the current behavior. No successor task or owner is needed for these two completed code tasks. The master roster and `tasks.md` remain unchanged; its batch findings await integration into the full 111-row reconciliation and independent review. This does not complete DG-04 task 2.1 or any other global task.

## Reproducible evidence

- Current main: `96632e91ad605970014d900686ae6f62e2762065`.
- Historical implementation/test commit: `140deb8e763f02dc27e811fdf2b48c9854da3fea` (`fix(log_failure): honour base-write-01 - --upstream, and name the file written`); verified as an ancestor of current main.
- Current spec: `openspec/specs/baseline-ownership/spec.md`, requirement `base-write-01` (line 32); summary table marks it `EXERCISED` against the current implementation and test paths (line 73).
- Current CI configuration: `.github/workflows/ci.yml` runs `python3 -m pytest tests/ -v` (line 87). The hosted workflow itself was not queried; this batch makes no claim about an individual hosted run.
- Direct behavior check in an isolated Linux container: `python3 tests/test_log_failure.py` — **12 tests passed**.
- `python3 scripts/regression_check.py --all` on the exact Linux-local main checkout — **passed**: no potential regressions, 0 hard-limit blockers, 0 scope gaps, and no package vulnerabilities. Existing file-size warnings remain in unrelated files.
- `python3 scripts/spec_traceability.py` — **261/303 requirements covered**, advisory reports 42 uncovered requirements; no hard error.
- `npx --yes @fission-ai/openspec@1.14.3 validate dg-04-archive-task-reconciliation --strict` — **passed**.
- `npx --yes @fission-ai/openspec@1.14.3 validate --all --strict` — **81 passed, 0 failed**.
- `scripts/spec_index.py --check` and `scripts/spec_state_gate.py` — **passed** at the current main snapshot.
- `npx --yes @fission-ai/openspec@1.14.3 validate --archived --strict --json` — **expected historical failure**: 50/60 archives validate; the ten incomplete historical task files remain unchanged. `2026-09-13-baseline-hygiene` still reports 12 unchecked boxes; this batch does not rewrite them.

## Source fingerprints at snapshot

These SHA-256 digests cover the exact Git blob bytes at the reviewed commit.

- Archived source `openspec/changes/archive/2026-09-13-baseline-hygiene/tasks.md`: `cd0db3203d4e03bea5d9cf451a24b23985ee7f099c0f6d579078285a8621096d`.
- Current implementation `scripts/log_failure.py`: `4543240f283b539aa01e7e1026d2c88d8b970d1ac953131719b7b6ef3e04f46b`.
- Current behavioral tests `tests/test_log_failure.py`: `fe3b7467770b74ce2f9eb297f95b5b62dcaf52350cae406e013f7ca0aaf35036`.
- Canonical spec `openspec/specs/baseline-ownership/spec.md`: `0c7ffaa71dc8dce537804e1a0e2b2bb348dc9b5266c1690ae7778e780e62e463`.
- CI workflow `.github/workflows/ci.yml`: `09faaca900d0f0e104741130293b28cf41d2ffc475fe8df7f14c741e0063deb3`.

The active task links this batch. The historical source and its checklist are preserved.