# aiggp-08 - stitcher proof parity

> Reopened 2026-11-06, re-measured 2026-11-13 at `690488a` (v1.3.36). Every
> box below was checked against the tree, not against the package's own claim.
> The original 2026-11-06 text ("Shipped in AIGGP `9c46180`: ...") is preserved
> in git history - `git show 690488a:openspec/changes/aiggp-08-stitcher-proof-parity/tasks.md`
> - and it does not hold: `9c46180` is the `add-gitlab-forge-support` commit
> and touches none of the action (`git show --stat 9c46180 --
> actions/stitcher-codereview` is empty), while every named file either
> arrived in the `c9d1194` vendoring of upstream v0.4.1 (2026-09-27) or has
> never existed in this repo's history. Per-stage verdicts, the commands that
> produce them, and what has changed since the 2026-10-25 reconciliation are
> in `measurement-2026-11-13.md`. No stage box may be ticked from the old
> claim; each needs its fixture, its wiring point and its evidence record.
>
> **Owner decision 2026-11-14 (decision 5 of the 2026-11-14 owner decision
> handoff; recorded from the handoff, which carries the owner's approval - this
> record does not assert the implementer verified it): own the vendored action,
> wire the seven present stages, build the two absent ones; evidence rides the
> GitHub adapter first, GitLab second.** The `measurement-2026-11-13` record
> stands, and every "Shipped in 9c46180" claim is retired.
>
> **Entry-move finding 2026-11-14.** `acceptance.md` Q12.1's hybrid starts with
> a reconcile of the parity branch `07aadb05` against current main. That branch
> is **not in this clone** - `git cat-file -t 07aadb05` reports no such object,
> and `git branch -a` lists nothing matching parity or stitcher. There is
> therefore nothing to cherry-pick and nothing to reconcile: by absence, every
> stage is re-implemented from current main (Q12.1's option B), and the entry
> step is recorded as unperformable rather than quietly skipped.
>
> **Completion record 2026-11-15.** All nine stages were implemented against
> current main under the owner decision above. Every stage carries an
> executable fixture (A-H below) with the seeded case it must catch. Tests
> live in `actions/stitcher-codereview/test/` (vitest 2.1.9, 41 tests);
> `scripts/run-tests.mjs` now selects the engine from the NEAREST package.json
> that declares vitest, so the nested suite runs in CI. Commands and results:
>
> ```
> cd actions/stitcher-codereview
> npm ci                                  # node_modules present here; CI runs this
> npm run build                           # exit 0 (tsc -p tsconfig.json)
> npx vitest run                          # exit 0 - 9 files, 41 tests passed
> cd ../..
> node scripts/run-tests.mjs              # 2448 passed, 1 env-only failure
>                                         # (tests/test_pi_extension_adapter.py needs
>                                         #  PI_SESSION_TSX, which CI sets; passes with it)
> node scripts/guardrails-scan.mjs        # exit 0 (pattern scan clean; warnings non-blocking)
> node scripts/semantic-scan.mjs          # exit 0 with typescript@5 (SEMANTIC-001/005 clean)
> python3 scripts/check_charset.py --repo .        # exit 0
> python3 scripts/check_encoding.py --repo .       # exit 0
> python3 scripts/check_corruption.py --repo .     # exit 0
> python3 scripts/check_exec_bits.py               # exit 0
> python3 scripts/regression_check.py --staged --pre-commit   # exit 0, 0 over hard limit
> python3 scripts/spec_traceability.py --root . --ratchet     # exit 0 (236/241 covered)
> python3 scripts/gen-checksums.py verify          # committed tree matches; the local
>                                         # working tree shows 3 mismatches from a
>                                         # concurrent session's uncommitted edits
> npx --no-install openspec validate --all --strict           # 49 passed, 0 failed
> ```

- [x] Stage 1: task traceability engine plus negative controls. *(`src/checks/commitMap.ts` maps commits to tasks in both directions and is wired through `src/checks/tasks.ts` and the engine when `--root` and `--base` resolve; a commit touching behavior with no covering task is `trace-orphan-commit` with file evidence, a done task with no implementing commit is `trace-orphan-task`, and an unresolvable range reports `trace-commits-unavailable` instead of a clean mapping it did not compute. Fixture A: `test/fixture-a-traceability.test.ts` - seeded orphan commit AND orphan task both reported, the mapped pair not reported, plus a real git-range run through `runReview`.)*
- [x] Stage 2: spec-to-diff review. *(`src/checks/specCompliance.ts` now attaches a deterministic `coh-ev-<digest>` reference per requirement verdict (`src/evidenceRef.ts`) and to the findings derived from it, so the verdict cites a coherence-shaped evidence record. An undeclared change is flagged `no-delta-specs` at high severity, so `decideVerdict` returns CHANGES_REQUESTED instead of a clean PASS. Fixture B: `test/fixture-b-spec-diff.test.ts` - undeclared change flagged with no clean verdict, coverage refs deterministic, and the negative control that a heuristic verdict can never claim VERIFIED.)*
- [x] Stage 3: reverse drift. *(`src/checks/drift.ts` gains `checkReverseDrift`: a changed behavior file whose capability gained no spec update in the same range is `drift-uncovered` at the bundle-declared severity (default medium, `--drift-severity`), naming the capability and file; unmapped files are `drift-uncategorized` low; no baseline reports `drift-no-baseline` instead of silence. Wired through `--drift-only` in `src/cli.ts`, `src/modes.ts`, and the repo gate `scripts/stitcher-drift.mjs`; the scheduled drift scan runs it as an advisory report and the blocking use is pre-commit (`scripts/stitcher-local.mjs`), where the diff belongs to the author. Fixture C: `test/fixture-c-reverse-drift.test.ts` - seeded silent behavior change reds the gate end-to-end, a spec update in range passes.)*
- [x] Stage 4: pre-commit local runner plus parity harness. *(`.pre-commit-hooks.yaml` declares hook id `stitcher-codereview` (`language: system`; the package is installed on PATH from this checkout, documented in the action README). `scripts/stitcher-local.mjs` is the parity harness: it normalizes verdict, findings and coverage, and in `--run` mode reviews the working tree and a clean `git worktree` at HEAD, classifying any divergence as a defect and exiting 1; a missing build fails closed at exit 2. Fixture E: `test/fixture-e-parity.test.ts` - the seeded local/CI divergence is caught and classified defect, identical verdicts pass, and `--run` catches an uncommitted working-tree change the clean CI worktree never sees.)*
- [x] Stage 5: SARIF emitter. *(`src/sarif.ts` attaches `properties.evidenceRef` to every result (and subject digest/head at run level), keeps adapter provenance in `properties.tool`, and preserves source-attributed rule ids. Fixture D: `test/fixture-d-sarif.test.ts` - schema-valid round-trip with locations and evidence links, refs and rules stable across serialize/parse, plus the negative control that the validator rejects a result with no message or rule id.)*
- [x] Stage 6: forge comment adapter. *(`src/vcs.ts` renders an evidence line per comment and refuses to emit a comment for a finding with no evidence reference (`unlinked` is reported separately); GitHub and GitLab `postReview` call `assertEvidenceLinked` BEFORE any API call, so a comment without a link SHALL NOT be posted. Fixture F: `test/fixture-f-comments.test.ts` - unlinked comments refused with the runner never called on both providers, linked comment posted. Named limit: no live forge credentials in this environment, so the provider path is exercised with a stub runner, not a real PR/MR.)*
- [x] Stage 7: whole-repo mode. *(`--scan <mode>` existed but nothing exercised it; `test/stages-wiring.test.ts` runs `--scan repository` end-to-end through the built CLI on a fixture repo and asserts a non-vacuous `repository-scan` record, and `.github/workflows/drift-scan.yml` runs it on the nightly full-tree sweep with a non-vacuity grep. Named limit: the scheduled workflow has not executed yet - it is wired, and its first run will be the live witness.)*
- [x] Stage 8: external-tool adapter interface plus first adapter. *(`src/checks/external-tools.ts` stamps every adapter-ingested finding with tool name, version (or `sha256:<12>` of the scanner file), input digest and raw-output digest, and derives an evidence reference from the raw output; check ids stay source-attributed. The Q12.2 combo is registered: `guardrails-scan` (parses `[GUARDRAILS][sev] RULE file:line - message`) and `secret-scan-declared` (declaration lines). Fixture G: `test/fixture-g-external-tools.test.ts` - identity preserved through parsing and through a live stub process, with the negative control that `missingIdentity` flags dropped name/version/digest. Named limit: the real fleet scanners are not invoked in-suite; the parsers take their real output shapes and the live path is exercised with a stub process.)*
- [x] Stage 9: agent-loop verdict endpoint. *(`src/verdict.ts` implements the promote/halt contract keyed to a subject digest: invalid digest halts; a loop re-presenting its own prior output (`--loop-outputs` contains the subject digest) re-enters as UNKNOWN and halts; CHANGES_REQUESTED halts; only an observed (TESTED/VERIFIED) PASS promotes. Exposed as `--verdict --subject-digest --producer` on the CLI. Fixture H: `test/fixture-h-verdict.test.ts` - loop self-certification halted, same digest from an independent observer promoted, digest keying proven, and the CLI endpoint exercised in `test/stages-wiring.test.ts`.)*

> **What is wired vs advisory.** Stages 2, 5, 6 and 9 run inside the review
> path itself. Stage 1 needs a resolvable `--root`/`--base` and reports
> `trace-commits-unavailable` otherwise. Stage 3's gate is blocking in
> pre-commit and in `scripts/stitcher-drift.mjs`; the nightly workflow runs it
> advisory because this repository's own tree is not yet drift-clean, and that
> choice is written in the workflow, not implied. Stage 7 runs on the nightly
> schedule. No stage claims a "Shipped in 9c46180" provenance, and none is
> ticked from one.
