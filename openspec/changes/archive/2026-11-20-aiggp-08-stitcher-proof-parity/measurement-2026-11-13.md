# aiggp-08 — nine-stage re-measurement, 2026-11-13

**Status: measurement record — not an acceptance decision.** Nothing in this
file ticks a task, and no requirement id in the package is wired to code,
traceability id or gate configuration.

Measured against AIGGP `main` at `690488a` (v1.3.36), 2026-11-13. This re-runs
`reconciliation.md` (measured 2026-10-25 at `8576940`) at the current head,
stage by stage against the nine task lines, and records what has changed since.
Every verdict below is a command that can be re-run from the repo root.

## The claim under test

Every box in `tasks.md` asserts "Shipped in AIGGP `9c46180`". `9c46180`
(2026-11-02) is the `add-gitlab-forge-support` commit, and it is not a
stitcher commit:

```
$ git log -1 --format='%h %ad %s' --date=short 9c46180
9c46180 2026-11-02 feat(forge,specs): implement add-gitlab-forge-support ...
$ git show --stat --format='' 9c46180 -- actions/stitcher-codereview
                       # empty — that commit touches none of the action
$ git ls-tree -r --name-only c9d1194 actions/stitcher-codereview | wc -l
37                     # every vendored file, all 37 of them
$ git ls-tree -r --name-only HEAD     actions/stitcher-codereview | wc -l
37                     # unchanged in count at HEAD
```

`c9d1194` (2026-09-27, PR #21) is the vendoring commit. Every file the nine
claims name was either vendored by it or has never existed here:

```
$ for f in src/checks/tasks.ts src/checks/specCompliance.ts \
           src/checks/drift.ts src/sarif.ts src/github.ts src/gitlab.ts \
           src/checks/external-tools.ts src/evidence.ts; do
    git log --oneline -- actions/stitcher-codereview/$f; done
c9d1194 ...                           # all eight, except drift.ts, which
34f00ce ...; c9d1194 ...              # also got a semantic-scan escape fix
$ for f in .pre-commit-hooks.yaml scripts/stitcher-local.mjs \
           actions/stitcher-codereview/src/verdict.ts \
           tests/test_stitcher_proof_parity.mjs; do
    git log --all --oneline -- "$f"; done
                        # empty, for all four, across every branch
```

Per-file lines, so the vendor commit is not taken on faith:

```
src/checks/tasks.ts                      c9d1194
src/checks/specCompliance.ts             c9d1194
src/checks/drift.ts                      34f00ce; c9d1194
src/sarif.ts                             c9d1194
src/github.ts                            c9d1194
src/gitlab.ts                            c9d1194
src/checks/external-tools.ts             c9d1194
src/evidence.ts                          c9d1194
src/cli.ts                               9544821 (exec bit); c9d1194
src/serve.ts                             c9d1194
```

## Per-stage verdict

| # | Stage | Claimed artifact | Measured at `690488a` | Verdict |
|---|---|---|---|---|
| 1 | Task traceability, both directions | `src/checks/tasks.ts` | present since `c9d1194`; `grep -n commit` → **no match**, so there is no commit mapping in either direction | partial, unwired |
| 2 | Spec-to-diff review | `src/checks/specCompliance.ts` | present since `c9d1194`; its `evidence: string[]` holds keyword strings (`keyword \`x\` in diff`, line 51), not coherence evidence references; no `coh-ev` anywhere | present, unwired |
| 3 | Reverse drift | `src/checks/drift.ts` | present since `c9d1194`; run by no gate here (`spec_gap_scan.py` covers spec→source, not changed-file→requirement) | present, unwired |
| 4 | Pre-commit runner + parity harness | `.pre-commit-hooks.yaml`, `scripts/stitcher-local.mjs` | neither exists anywhere in this repo's history; `package.json` `files` names `.pre-commit-hooks.yaml` but the vendored set is `action.yml NOTICE.md package.json package-lock.json README.md src tsconfig.json` | absent |
| 5 | SARIF emitter | `src/sarif.ts` | present since `c9d1194`; `grep -n evidence src/sarif.ts` → no match; properties carry `ruleId`/`ruleIndex` only | present, unwired |
| 6 | Forge comment adapter | `src/github.ts`, `src/gitlab.ts` | present since `c9d1194`; `grep -n evidence` → no match; the spec's refusal case (no evidence link ⇒ no comment) has nothing to satisfy it | present, unwired |
| 7 | Whole-repo mode | `--whole-repo` / `scan: repository` | `src/cli.ts:140` has `--scan <mode>` `off\|repository`; `README.md:98` documents `scan: off \| repository`; no test, no wiring, no scheduled run | partial, unwired |
| 8 | External-tool adapters, identity kept | `src/checks/external-tools.ts` | present since `c9d1194`; `parseSemgrep`/`parseTrivy`/`parseOsv` take raw stdout and drop it — tool name survives, version and raw-output digest do not | present, unwired |
| 9 | Agent-loop verdict endpoint | `src/verdict.ts` | never existed here (`git log --all` empty); `grep -rn 'promote\|halt\|subjectDigest' src/` → no match | absent |

Counts, stated plainly: **7 present (5 fully — stages 2, 3, 5, 6, 8 — and 2
partial — stages 1 and 7), 2 absent (pre-commit runner, agent-loop contract),
0 wired, 0 tested in-tree, 0 behind the evidence contract, 0 of Fixtures A–H
present.** The earlier record's own count line read "6 present (5 fully, 2
partially), 2 absent"; the rows it summarised were always 7 present and 2
absent, and this line is the corrected arithmetic against the same rows.

The vendored `package.json` declares `test: vitest run`, `mutate: node
scripts/mutate.mjs`, `bench: node bench/run.mjs`, `smoke: node
scripts/smoke-pack.mjs` — and `test/`, `tests/`, `scripts/`, `bench/`, `dist/`
and `openspec/` are **all absent from the vendored copy**, so not one declared
script can run here.

## What is wired

Nothing, and the search is not narrow:

```
$ grep -rn stitcher .github/ scripts/ tests/ package.json | grep -v '^actions/'
                       # no output
$ grep -rniI stitcher /mnt/data/git/missioncontrol \
      --include='*.yml' --include='*.json' --include='*.sh' ...
                       # no output
```

`MergeKingdom` and `agent-guardrails-template` mention `stitcher-codereview`
only as a **repository URL inside fleet-sweep result JSON** (e.g.
`"https://github.com/TheArchitectit/stitcher-codereview"`); neither invokes
the action in a workflow or gate script.

## Deltas since the 2026-10-25 record

1. **The size-gate blind spot the reconciliation surfaced is closed.**
   `ef0a8ca` (v1.3.35) added `actions/`, `fleet-manager/`, `templates/` and
   `engines/` to the walk. `python3 scripts/regression_check.py --all
   --pre-commit` now prints `0 scope gaps` and, among 11 pre-existing oversize
   warnings, `actions/stitcher-codereview/src/serve.ts (558 lines, limit 500)`
   — exit 0. The 558-line file is visible now; it is still over the hard
   limit, and the warning says so.
2. **The upstream fork carries the test suite this repo lacks.** In
   `/mnt/data/git/stitcher-codereview-collab` at `8cef394`, `tests/` holds 26
   vitest files and `.pre-commit-hooks.yaml` exists (added `248f6b8`), and
   `serve.ts` has been split under the budget. Neither
   `scripts/stitcher-local.mjs` nor `src/verdict.ts` has ever existed there
   either. This is the evidence the own-or-fork decision needs: stages 1–3,
   5, 6 and 8 have tests upstream, none here.
3. **Everything else is unchanged:** 0 wired, 0 in-tree tests, 0 evidence
   adapter, Fixtures A–H absent (`acceptance.md` was re-checked: still none).

## What would close a stage

- **Wiring** — a workflow or script in this repo that runs the action. This is
  the owner's wire-or-drop decision, not a coding step.
- **Fixtures A–H** with their negative controls — new work in whichever repo
  owns the reviewer. Per `design.md`, "no fixture, no merge".
- **The evidence adapter** (`src/evidence.ts` → a coherence bundle +
  attestation) — the one genuinely missing seam; without it a finding cannot
  be cited the way `coh-ev-*` requires, and the package's own precondition
  ("feature completeness without evidence is not delivery") fails.

## Owner decisions this measurement leaves where they were

1. **Own or fork** the reviewer: pin and re-vendor with its test suite, or
   re-implement the pieces wanted against the shipped gates.
2. **Wire or drop** the in-tree action; no consumer repo invokes it.
3. **Who owns the evidence adapter** if the action is kept.
4. **Scope**: `actions/` is in the size gate now; decide whether the 558-line
   file is to be split or the warning accepted.
5. **Which repo owns the reviewer** for the three absent pieces.

**Precedence:** the shipped ladder wins. This record creates no wiring, and
the nine boxes stay open until the decisions above are made and the features
are delivered with their fixtures.
