# Evidence at Scope Review

## Baseline

- Exact source snapshot: `ac61e20fa7a4afcc8e2827817446fa01cb5730ff`.
- Read-only review found three workflow files with runtime `.devgate/` usage and recursive submodule checkout: `templates/github-workflows/drift-scan.yml`, `specs.yml`, and `text-integrity.yml`.
- `spec-coherence.yml` has a distinct in-tree bootstrap at lines 164-190 and is not included in this finding. `bundle-size-check.yml` and `file-size-check.yml` mention `.devgate` in comments but do not invoke it at runtime.
- No live consumer workflow was launched and no external repository, credential, or runner was used.

## Source anchors

- `templates/github-workflows/drift-scan.yml:49-59,109-139` checks out recursively, then invokes `.devgate/scripts/` entry points.
- `templates/github-workflows/specs.yml:64-67,102-126` checks out recursively, then executes the strict negative control, traceability checks, and gap scanner from `.devgate/scripts/`.
- `templates/github-workflows/text-integrity.yml:69-94,102-116,136-144` sets `.devgate/scripts`, checks out recursively, runs charset/encoding/corruption checks, and dispatches declared `.devgate/tests/` controls.

## Acceptance boundary

This baseline section is scope evidence only. At the time recorded, DG-08 implementation tasks remained unchecked and none of the affected workflow jobs had yet been accepted through a clean consumer run.

## Writer evidence at implementation

- Source revision: `6b08ee17b1309aba241f7156b9b9277fb37e4270`; work was performed in a detached sibling worktree, not the lead checkout.
- `tests/test_github_workflow_bootstrap.py` executes the extracted setup bodies for both drift jobs, specs, and text integrity against disposable consumers and local bare fake-approved-source repositories. No `.gitmodules` is created and no network URL is used. The fixtures exercise real Git fetch/checkout and verify the pinned `HEAD`, `.devgate/` root, ignored/tracking state, and required-file declarations.
- Offline focused controls: `python3 -m pytest -q tests/test_github_workflow_bootstrap.py` — **28 passed**. The separate root-control run `python3 -m pytest -q tests/test_github_workflow_bootstrap.py -k wrong_dev_gate_root` — **4 passed, 28 deselected**. Negative controls cover malformed SHA, wrong existing commit/root, partial `.devgate/`, missing workflow-specific source file, consumer-tracked `.devgate/`, dirty reuse, and failed Git root inspection. Every negative asserts nonzero setup and no `gate.green` marker.
- Strict OpenSpec validation: `/opt/toolchain/node_modules/.bin/openspec validate --all --strict` — **76 passed, 0 failed**.
- Final reruns after updating task status and setup diagnostics: strict OpenSpec validation — **76 passed, 0 failed**; malformed-pin diagnostic control — **4 passed, 28 deselected** across the drift resolver, drift scan, specs, and text-integrity setup blocks.
- Test floor: `python3 tests/gen_floors.py` — **144 suites / 2,110 tests; floors hold** at the time of that check.
- Directory scan: `rg -n --glob '*.yml' '\.devgate/(scripts|tests)/' templates/github-workflows` found runtime calls in the three changed workflows; `spec-coherence.yml` has its own existing bootstrap. Other hits were explanatory comments in bundle/file-size templates. No additional runtime workflow without a bootstrap was found.
- `git diff --check` passed. The workflow diff retains the existing action SHAs, permissions, runner expressions, dependency pins, named gate commands, and `fetch-depth: 0` for both history-dependent scans.
- **Integrated full suite and writer gates: NOT_RUN to completion.** A full `python3 -m pytest tests/ -q` run was started, showed failures before 13% progress, and was stopped after lead requested avoiding duplicate full-suite work. It has no completed exit status or adjudicated failure list. Lead owns the integrated rerun; do not read the partial run as a pass or a final failure verdict.
- DG-08 task 1.6 remains open pending the integrated suite and writer gates; the full suite has no completed result.

### Follow-up: drift scanner dependency coverage

- Lead review identified that the scheduled drift job's preflight did not require the silent-success rules/allowlist, scope, and shared scanner helpers, while its gate treats absent rules as a clean no-op. The resolve-target job was also carrying unrelated scanner files.
- Moved resolve-target setup into its own `Bootstrap pinned DevGate for target detection` step before the unchanged `Detect host CI / runner info` step. That preflight requires only `scripts/detect-host-ci.py`; the scheduled drift job preflights the full scanner dependency list, including `.guardrails/prevention-rules/silent-success-rules.json`, `.guardrails/silent-success-allowlist.json`, `.guardrails/scope.json`, and shared Python/Node runtime helpers.
- Added `test_drift_scan_job_fails_closed_when_silent_success_rules_are_missing`, which names the second drift job and missing rules file. Changed workflow step extraction to exact names so this test cannot accidentally select the target-detection job.
- Lead's prior integrated run found four existing runner-resolution failures because bootstrap had been embedded in the `Detect host CI / runner info` run block. After moving setup into the separate step, `python3 -m pytest -q tests/test_drift_scan_template.py tests/test_github_workflow_bootstrap.py` passed: **38 passed**.
- Follow-up strict OpenSpec validation: `/opt/toolchain/node_modules/.bin/openspec validate --all --strict` — **76 passed, 0 failed**.
- The integrated repository suite and test-floor check remain with lead; the earlier full suite was stopped before completion and does not provide a result for these final bytes.

### Follow-up: raw pinned blob verification

- A separate audit found that Git's `assume-unchanged` and `skip-worktree` flags can suppress status output for modified tracked files. Each of the four bootstrap blocks now resolves the pinned blob for every required path with checked `git rev-parse --verify "$DEVGATE_SHA:$required"`, hashes the actual regular file bytes with checked `git hash-object --no-filters -- "$required"`, and fails explicitly if the hashes differ. Existing tracked-path and regular-file checks remain in place.
- Fresh checkout uses command-scoped `-c core.autocrlf=false` so inherited autocrlf configuration does not transform checkout bytes before raw-blob verification. No consumer-wide Git configuration is changed; reuse still fails on byte drift.
- Added `test_assume_unchanged_required_file_drift_fails_closed` across all four bootstrap blocks. It alters an innocuous comment after setting `assume-unchanged` and confirms bootstrap stops before the gate. Added a fresh-checkout control with global `core.autocrlf=true`.
- Focused local rerun: `python3 -m pytest -q tests/test_github_workflow_bootstrap.py tests/test_drift_scan_template.py` — **46 passed**.
- Independent review approved the raw-blob/autocrlf implementation and real gate/negative controls. The integrated full suite, test-floor, and writer gates are still lead-owned and pending; task 1.6 remains open.
- `git diff --check` passed for the follow-up.

## Independent and integrated laptop verification

Independent review exercised all four setup blocks at the real DevGate pin
`6b08ee17b1309aba241f7156b9b9277fb37e4270`. The drift scanner, specs workflow,
and text-integrity workflow completed their named gates on disposable
consumers. The text-integrity controls passed 55 tests. A consumer missing
its charset policy and setups with altered required bytes failed before
readiness.

On the laptop's Docker Desktop Linux engine, the integrated source tree
`50c65be36822c9a88fc98b48e38627c7edd62383` passed 2,115 Python tests with 13
skips and 189 passing subtests. Fleet manager passed 422 tests. The per-file
runner finished with 2,524 passed and zero failed across 172 files. The new
bootstrap suite timed out in the parallel pass and passed all 41 tests on
the runner's automatic solo retry. The final floor check collected 2,128
tests in 145 suites.

Strict validation with the repository's pinned OpenSpec CLI passed all 76
items on the integrated active tree. The lead pattern, semantic, full-tree
and staged regression, and silent-success scans passed. Hosted consumer
workflow evidence remains unavailable.
