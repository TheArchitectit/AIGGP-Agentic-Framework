# aiggp-08 - stitcher proof parity

> Reopened 2026-11-06, re-measured 2026-11-13 at `690488a` (v1.3.36). Every
> box below was checked against the tree, not against the package's own claim.
> The original 2026-11-06 text ("Shipped in AIGGP `9c46180`: …") is preserved
> in git history — `git show 690488a:openspec/changes/aiggp-08-stitcher-proof-parity/tasks.md`
> — and it does not hold: `9c46180` is the `add-gitlab-forge-support` commit
> and touches none of the action (`git show --stat 9c46180 --
> actions/stitcher-codereview` is empty), while every named file either
> arrived in the `c9d1194` vendoring of upstream v0.4.1 (2026-09-27) or has
> never existed in this repo's history. Per-stage verdicts, the commands that
> produce them, and what has changed since the 2026-10-25 reconciliation are
> in `measurement-2026-11-13.md`. Nothing is ticked: the package's own rule is
> that "feature completeness without evidence is not delivery", and no stage
> has a fixture, a wiring point or an evidence record.

- [ ] Stage 1: task traceability engine plus negative controls. *(Partial, unwired. `actions/stitcher-codereview/src/checks/tasks.ts` has been in-tree since `c9d1194` and contains no commit mapping at all — `grep -n commit` is empty — so the bidirectional requirement ("every commit SHALL map to covering spec tasks or be reported as uncovered") is unimplemented; `tests/test_stitcher_proof_parity.mjs` has never existed, and Fixture A has no witness.)*
- [ ] Stage 2: spec-to-diff review. *(Present, unwired. `src/checks/specCompliance.ts` has been in-tree since `c9d1194`; its `evidence: string[]` holds keyword-overlap strings, and there is no coherence evidence reference (`grep -n 'evidence\|coherence\|coh-ev'` finds only the keyword array). No gate runs it.)*
- [ ] Stage 3: reverse drift. *(Present, unwired. `src/checks/drift.ts` has been in-tree since `c9d1194` (plus a `34f00ce` escape fix); no workflow or script runs it, and `spec_gap_scan.py` covers spec→source, not changed-file→requirement. Fixture C has no witness.)*
- [ ] Stage 4: pre-commit local runner plus parity harness. *(Absent. `.pre-commit-hooks.yaml` and `scripts/stitcher-local.mjs` have never existed in this repo (`git log --all` is empty for both); the vendored `package.json` names the hook file in `files` but it was not vendored, and its `test`/`mutate`/`bench`/`smoke` scripts point at `test/`, `scripts/` and `bench/`, none of which was vendored. The upstream fork carries a `.pre-commit-hooks.yaml` (`248f6b8`) but no parity harness. Fixture E has no witness.)*
- [ ] Stage 5: SARIF emitter. *(Present, unwired. `src/sarif.ts` has been in-tree since `c9d1194`; `grep -n evidence` is empty, so no evidence reference is attached to a result. Fixture D has no witness.)*
- [ ] Stage 6: forge comment adapter. *(Present, unwired. `src/github.ts` and `src/gitlab.ts` have been in-tree since `c9d1194`; `grep -n evidence` is empty, so the requirement's refusal case — a comment without an evidence link SHALL NOT be posted — has nothing to satisfy it. Fixture F has no witness.)*
- [ ] Stage 7: whole-repo mode. *(Partial, unwired. `src/cli.ts:140` accepts `--scan <mode>` `off|repository` and `README.md:98` documents `scan: off | repository`; no test exercises it and no scheduled or on-demand run exists. This is not the `scripts/stitcher-local.mjs` the original claim named.)*
- [ ] Stage 8: external-tool adapter interface plus first adapter. *(Present, unwired. `src/checks/external-tools.ts` has been in-tree since `c9d1194`; `parseSemgrep`/`parseTrivy`/`parseOsv` take raw stdout and drop it — the tool name survives, its version and raw-output digest do not — and the Q12.2 combo targets (`guardrails-scan.mjs`, `secret-scan-declared.sh`) are not adapted. Fixture G has no witness.)*
- [ ] Stage 9: agent-loop verdict endpoint. *(Absent. `actions/stitcher-codereview/src/verdict.ts` has never existed here or upstream, and `grep -rn 'promote\|halt\|subjectDigest' src/` is empty: no promote/halt contract and no subject-digest keying. Fixture H has no witness.)*
