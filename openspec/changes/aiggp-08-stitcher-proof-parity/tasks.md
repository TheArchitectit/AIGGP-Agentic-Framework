# aiggp-08 - stitcher proof parity

> Reopened 2026-11-06. Every box in these tasks was checked against AIGGP
> `9c46180`. Measured: `9c46180` is the GitLab-forge commit, none of the
> claimed files (`.pre-commit-hooks.yaml`, `scripts/stitcher-local.mjs`,
> `verdict.ts`, `tests/test_stitcher_proof_parity.mjs`) exists anywhere in
> AIGGP history, no workflow runs the action, and no published spec names it.
> The only in-tree artifact is the vendored upstream action
> `actions/stitcher-codereview/` (v0.4.1, vendored 2026-09-27 without a
> package). Each stage below is re-checked against the tree; nothing re-checked
> yet. The tracker entry left `devgate-open-changes` with its work undone --
> this file is where it is tracked.

- [ ] Stage 1: task traceability engine plus negative controls. *(Shipped in AIGGP `9c46180`: `actions/stitcher-codereview/src/checks/tasks.ts` commit-keyed task traceability + negative controls in `tests/test_stitcher_proof_parity.mjs`)*
- [ ] Stage 2: spec-to-diff review. *(Shipped in AIGGP `9c46180`: `actions/stitcher-codereview/src/checks/specCompliance.ts` wired with coherence evidence references + tested in `tests/test_stitcher_proof_parity.mjs`)*
- [ ] Stage 3: reverse drift. *(Shipped in AIGGP `9c46180`: `actions/stitcher-codereview/src/checks/drift.ts` reverse drift detection + tested in `tests/test_stitcher_proof_parity.mjs`)*
- [ ] Stage 4: pre-commit local runner plus parity harness. *(Shipped in AIGGP `9c46180`: `.pre-commit-hooks.yaml`, `scripts/stitcher-local.mjs`, and local/CI parity harness in `tests/test_stitcher_proof_parity.mjs`)*
- [ ] Stage 5: SARIF emitter. *(Shipped in AIGGP `9c46180`: `actions/stitcher-codereview/src/sarif.ts` emits SARIF 2.1.0 with coherence evidence references + tested in `tests/test_stitcher_proof_parity.mjs`)*
- [ ] Stage 6: forge comment adapter. *(Shipped in AIGGP `9c46180`: `actions/stitcher-codereview/src/{github.ts,gitlab.ts}` validates coherence evidence links + tested in `tests/test_stitcher_proof_parity.mjs`)*
- [ ] Stage 7: whole-repo mode. *(Shipped in AIGGP `9c46180`: `--whole-repo` / `scan: repository` mode in `scripts/stitcher-local.mjs` and `actions/stitcher-codereview/src/index.ts` + tested in `tests/test_stitcher_proof_parity.mjs`)*
- [ ] Stage 8: external-tool adapter interface plus first adapter. *(Shipped in AIGGP `9c46180`: `actions/stitcher-codereview/src/checks/external-tools.ts` with pinned tool version and raw-output digest reference + tested in `tests/test_stitcher_proof_parity.mjs`)*
- [ ] Stage 9: agent-loop verdict endpoint. *(Shipped in AIGGP `9c46180`: `actions/stitcher-codereview/src/verdict.ts` subject-digest-keyed promote/halt verdict contract + tested in `tests/test_stitcher_proof_parity.mjs`)*


