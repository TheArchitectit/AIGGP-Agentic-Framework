# DG-04 archive reconciliation evidence

## Reproducible inventory snapshots

The original review snapshot is commit `f5807ad` (`docs(openspec): audit AIGGP evidence and propose item-level changes`), which introduced this active change. Counting archive directories and task markers in the Git tree at that commit reproduces the proposal's baseline: 43 archive IDs and 829 ordinary `[x]` / `[ ]` task rows, of which 719 are checked and 110 unchecked. There is also one `[~]` partial-status row in `2026-10-01-devgate-spec-coherence-service`; the proposal's 829-row figure counts ordinary checked/unchecked boxes and omits that third state.

At the intermediate review revision `4bc3f050c7178c8642fb38738b0a4328329c13d9`, the tree contained 56 archive IDs and 899 ordinary rows: 789 checked and 110 unchecked, plus the same one `[~]` row. The current ready revision `0921b11e5c8bf81a1f6231c7dc6d73c06b157402` contains 58 archive IDs and 907 ordinary rows: 797 checked and 110 unchecked, plus one `[~]` partial row (908 total task records). The 15 archive directories added since `f5807ad` account for 78 additional checked boxes; the unchecked and partial counts are unchanged. `git diff --name-only --diff-filter=MDR f5807ad 0921b11 -- openspec/changes/archive` returned no paths, so none of the original 43 archive package files was modified or deleted. The continuation worktree also has no archive-path changes.

Counts were produced from `git ls-tree -d --name-only <revision>:openspec/changes/archive` and each archived `tasks.md` blob via `git show`, classifying task lines with `^\s*- \[([ xX~])\]`. Current strict validation below independently confirms the current archive count and identifies the archive IDs with incomplete historical state.

## Ten archived strict-validation failures

Repository-pinned OpenSpec 1.14.3 `openspec validate --archived --strict --json` reports 58 archive changes, 48 valid and 10 invalid. The same ten historical task-state failures remain; the added two packages validate. These ten failures are not proof by themselves that the underlying work is undone or done. Original proposal/audit pointers are recorded here; this bounded pass does not claim task-level code/test verification or assign successor owners. Until that review exists, retain the original statuses and treat disposition as **unsubstantiated / not adjudicated**.

| Archived change | Strict result | Stable original issue / disposition evidence |
| --- | --- | --- |
| `2026-09-13-baseline-hygiene` | 12/12 incomplete | `openspec/changes/archive/2026-09-13-baseline-hygiene/proposal.md` cites `docs/qa/2026-09-13-full-qa.md` findings H3, H8, M8, L6; proposal status is Proposed. |
| `2026-09-13-ci-templates-docs` | 13/13 incomplete | Archived proposal cites the same QA report findings H2, M4, M7, M9, M10, L3, L4, L5; status is Proposed. |
| `2026-09-13-deploy-pipeline` | 15/15 incomplete | Archived proposal cites QA findings C6, C7, H7, M5, M6, L8; status is Proposed. |
| `2026-09-13-gate-correctness` | 20/20 incomplete | Archived proposal cites QA findings C1–C5, H4, H5, L1, L7; status is Proposed. |
| `2026-09-13-rule-enforcement-gaps` | 16/16 incomplete | Archived proposal cites QA findings H1, H6, M1, M2, M3; status is Proposed. |
| `2026-09-13-runner-monitor` | 15/15 incomplete | Archived proposal records the 2026-09-12 stalled `example-runner` incident and owner request; status is Proposed. It has no `Source audit` finding list. |
| `2026-10-01-devgate-spec-coherence-service` | 3/93 incomplete to validator | 90 checked, 2 unchecked, and one `[~]` row. The partial row explicitly says real arm64 pilots were not run and must not be treated as a pending lead action; another unchecked row is Stage 3 readiness. No per-row successor disposition is established here. |
| `2026-10-03-fix-specs-gate-audit-2026-09` | 2/62 incomplete | Two archived task rows remain unchecked. The archived proposal records the gate-audit findings; no task-to-current-test mapping was completed in this pass. |
| `2026-10-13-add-oap-evidence-consumer` | 12/18 incomplete | Archived proposal explicitly says proposed and blocked on OAP native authority readiness; it does not establish deployed authority or live verification. |
| `2026-10-13-harden-oap-evidence-verification` | 3/16 incomplete | Archived proposal says this is a proposed remediation specification only and no remediation is implemented by that package. Do not infer code completion from related work. |

The ten strict failures account for 110 unchecked rows plus the one `[~]` partial row. No archive task was marked complete and no implementation was claimed from a checked box. Task-level evidence mapping, successor ownership, and independent review remain open.

## Archived delta capability reconciliation

At ready commit `0921b11`, the 58 archive packages contain 64 delta capability directories representing 58 unique capability names. Current comparison surfaces are 65 canonical capability directories and 11 unique active delta names. The new [`delta-capability-reconciliation.md`](delta-capability-reconciliation.md) assigns stable `ARC-CAP-001` through `ARC-CAP-058` IDs, records each archived spec path and archive-path Git history commit, checks exact canonical/active names and parsed requirement-ID overlap, and flags name-only or ID-only successors separately. Internal-link validation resolved all 121 Markdown links in that crosswalk.

The six historical-only names were checked against actual records. `openspec-format-conformance` maps `spec-fmt-04` to current `requirement-id-inventory`; `runner-image-cycling` and `secret-scanning` are called shipped in the 2026-10-03 disposition note but have no same-name canonical spec; the OAP proposals remain explicitly proposed/blocked or unimplemented; `scanner-root-anchoring` has source/CI evidence but no current same-ID canonical/active mapping or explicit retirement decision. These are name/ID dispositions only, not task completion. In particular, no task was marked implemented solely because its archived checkbox is checked.

## Commands and results

- `npx --yes @fission-ai/openspec@1.14.3 validate --archived --strict --json` — **failed as expected**: 48/58 valid; the same ten historical task-state failures remain.
- `npx --yes @fission-ai/openspec@1.14.3 validate --all --strict` — **passed**: 75/75 canonical specs and active changes.
- Current task-row inventory from committed Git objects — **passed**: 58 archive IDs, 907 ordinary rows (797 checked / 110 unchecked), and one separate `[~]` partial row.
- Baseline preservation check — **passed**: no modified/deleted original archive paths between `f5807ad` and `0921b11`; no archive files changed in this continuation worktree.
- Crosswalk shape/link check — **passed**: 58 stable capability rows for 64 delta directories and 121/121 internal links resolve.
- Complete per-row implementation/test/CI/history review for all 110 unchecked rows — **NOT_RUN**; the later bounded source-evidence increment covers only selected rows and leaves task 2.1 open. Independent inventory and link review passed. Independent review of the complete per-task disposition remains pending.
- Required `python3 scripts/regression_check.py --all` — **passed** in a disposable canonical-LF Git checkout from the ready commit, with the three current documentation files as the tagged diff: no potential regressions, 0 hard-limit findings, 0 scope gaps, and no package vulnerabilities. The scan skipped 125 added prose lines and reported only pre-existing file-size warnings.

## Stable task-disposition roster (task 2.1 remains open)

[`unchecked-task-roster.md`](unchecked-task-roster.md) assigns stable `ARC-TASK-001` through `ARC-TASK-111` IDs to all 110 original unchecked rows and the single original `[~]` partial row, sorted by archive package and source line. Each row links to its exact archived `tasks.md` source line and proposal; where established, it also links historical QA or the strict-validation record. The roster records row-specific historical context for the coherence-service partial and readiness row, the two gate-audit rows, and both OAP proposals. It explicitly marks every row `unadjudicated`, preserves the partial marker in the source, and records the missing current implementation/test/CI evidence or external-owner proof without assigning a real owner. It notes that no live runner/token or network test was performed.

The roster is an inventory scaffold, not the required per-row adjudication. Focused review of all 111 entries against current implementation, tests, CI, documentation, and commit history is incomplete; therefore task 2.1 remains unchecked. Task 2.2 remains unchecked because no confirmed live successor/owner route was established, and task 2.3 remains unchecked pending independent review and the archived strict validation recheck. No archive bytes or task markers were changed.

- Roster row count and stable-ID generation — **passed**: 110 unchecked + 1 partial = 111; source-line IDs are deterministic for the ready snapshot.
- Roster internal links — **passed**: 111 source links resolve to existing archived task files; stable ID and link counts match 111 roster rows.
- Per-row implementation/test/CI/history adjudication — **NOT_RUN**; required before task 2.1 can be checked.
- Live external tests and real owner assignment — **NOT_RUN / not performed**.

## Bounded current-source evidence increment

[`current-source-evidence.md`](current-source-evidence.md) records specific #41 source/test matches for `ARC-TASK-001`–`002` and `ARC-TASK-041`–`043`, points to the present CI/deployment source surfaces for `ARC-TASK-013`–`040` without overstating row-level proof, and distinguishes runner-enrollment fixture coverage from unavailable live-hub/host state. It separately preserves the arm64 hardware gate and pilot partial state (`ARC-TASK-092`–`094`), dated owner-dependent runner host observations (`ARC-TASK-095`–`096`), and local OAP evidence versus missing native authority, deployed transport, and independent approval (`ARC-TASK-097`–`111`). These are bounded row findings; task 2.1 remains unchecked until all 111 records have complete per-row evidence disposition and review.

- `python3 tests/test_log_failure.py` in `aiggp-pr41-lead:20261125` — **passed**, 12 tests.
- `node tests/test_scanner_root_anchor.mjs` in `aiggp-pr41-lead:20261125` — **passed**, all root-anchor controls.
- `node tests/test_run_tests_runner.mjs` in `aiggp-pr41-lead:20261125` — **passed**, 12/12.
- Writer’s Python pytest invocation — **NOT_RUN**: its Bash login shell selected the system interpreter and omitted the bundled pytest environment.
- Writer’s strict OpenSpec rerun — **NOT_RUN**: its Bash login shell omitted the bundled OpenSpec executable. The initial strict result above predates this increment.
- Archive preservation check — **passed**: no modified/deleted archive paths between `f5807ad` and ready #41 `0921b11`; no archive edits in this worktree.
- #41 hosted CI — lead-reported green; this pass did not retrieve hosted details or map an individual run to every historical row.
- arm64 hardware, live runner fleet/hub, OAP service/operation, GitHub API, and external owner decisions — **NOT_RUN** by scope.

## Independent integration checks

The 111 archived row pointers, 64 archived delta paths, 58 stable capability
IDs, first-addition history, and internal links were checked against ready
`0921b11`. Separate pinned archival validation reproduced 48 valid and ten
historic task-state failures. The original archive paths remained intact.

A canonical LF checkout of the follow-up base `7ec9983` ran the bundled
pytest explicitly in a network-disabled Linux container. Logger, runner
enrollment, GitLab deployment, and OAP signature/schema fixtures reported
101 passed and 107 subtests passed. These are local fixture results. Live
runner and OAP acceptance and the rest of task 2.1 remain open.
