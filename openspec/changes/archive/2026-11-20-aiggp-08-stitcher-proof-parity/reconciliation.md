> **Re-anchored 2026-10-02:** `aiggp-00`/`aiggp-09` are retired (see `openspec/changes/AIGGP-RETIREMENT-2026-10-02.md`); references below read against DevGate's shipped evidence machinery (`hub/coherence/`) and runner enrollment (`scripts/runner-enroll.sh`).

# AIGGP-08 ↔ today's DevGate tree: feature reconciliation

**Status: reconciliation record — not an acceptance decision.** Measured
2026-10-25 against AIGGP `main` at `8576940`. Nothing below is taken from the
draft's own claims; every row is read from the tree.

**The headline, and why the package's premise needed re-reading.** AIGGP-08
proposes to "promote the proof-strengthening subset of Stitcher parity into the
DevGate module". Most of that subset is **already in the tree** — not as nine
promoted features, but as a **vendored upstream action**:
`actions/stitcher-codereview/`, version 0.4.1, MIT, vendored from upstream
commit `28e0bfe925fb` in `c9d1194` (2026-09-27, PR #21), 5,739 lines of
TypeScript with `action.yml`, `package.json`, `package-lock.json`,
`tsconfig.json` and `src/` (`NOTICE.md` records the attribution and the three
`guardrails-allow` comments added to satisfy this repo's own scan). So the
disposition is neither "unbuilt" nor "shipped as designed": **six of the nine
features exist as third-party code in-tree, none of them is wired to anything,
none emits a DevGate evidence record, and not one has a negative control.**

**What was measured, and how.** Read in full: `action.yml`, `NOTICE.md`,
`package.json`, `README.md`, `src/cli.ts`, `src/evidence.ts`, `src/sarif.ts`,
`src/checks/{specCompliance,drift,tasks,external-tools}.ts`, the exported
surface of `src/github.ts` and `src/gitlab.ts`. Searched: `.github/workflows/`
for any reference to the action (none), `tests/` for any test naming it (none),
`package.json`'s declared scripts against the vendored file set, and the size
gate's scope (`gate_common.load_source_dirs` and
`regression_sizes.check_scope_coverage`) against the directory it lives in.

## The nine promoted features

| # | Feature (stage) | In the tree | Disposition | The gap that decides it |
|---|---|---|---|---|
| 1 | OpenSpec-to-diff review, verdict per requirement (2) | `src/checks/specCompliance.ts` → `requirementCoverage[]`, one entry per requirement id, with `blocker`/`high` findings (`findingsForCoverage`) | **present, unwired** | Verdicts are keyword-overlap heuristics (optionally blended with an LLM); nothing in this repo proves them |
| 2 | Reverse drift (3) | `src/checks/drift.ts` — `drift-uncovered` (medium), `drift-uncategorized` (low), one `info` when there is no baseline | **present, unwired** | Not run by any gate here; `spec_gap_scan.py` covers spec→source, not changed-file→requirement |
| 3 | Bidirectional task traceability (1) | `src/checks/tasks.ts` — `task-done-no-evidence`, `task-undone-with-evidence`, `no-tasks-file` | **partial** | Task side only, against diff text; **no commit mapping in either direction** ("every commit SHALL map to covering spec tasks or be reported as uncovered" is not implemented anywhere) |
| 4 | SARIF output (5) | `src/sarif.ts` (`ruleId`, `level`, `physicalLocation`) + `action.yml` uploads via SHA-pinned `codeql-action`, best-effort | **present, unwired** | No evidence reference in the SARIF (`evidence.ts`'s bundle is not attached); upload is deliberately `continue-on-error`, so it cannot gate |
| 5 | Pre-commit mode, identical verdicts to CI (4) | README documents `.pre-commit-config.yaml` pointing at the **upstream** GitHub repo | **not shipped** | `.pre-commit-hooks.yaml` is listed in `package.json`'s `files` but is **not vendored**; no parity harness, no identical-verdict fixture. (DevGate's own `regression_check.py --pre-commit` is a different gate and does not run this reviewer) |
| 6 | Whole-repo mode (7) | config key `scan: off \| repository` — "whole-tree drift scan" | **partial, unwired** | Config-gated, no CLI flag, no test; nothing exercises it in-tree |
| 7 | External-tool adapters, identity preserved (8) | `src/checks/external-tools.ts` — semgrep, osv-scanner, trivy, each with its own `checkId`, severity clamped, never re-labelled | **present, unwired** | Tool **name** survives; **version and raw-output reference do not** (the raw stdout is parsed and dropped) |
| 8 | Forge review comments (6) | `src/github.ts`, `src/gitlab.ts`, `--post none\|github\|gitlab\|vcs`, inline + summary when `comment: true` | **present, unwired** | Comments carry rule/severity/location; **no evidence link** — the requirement's own refusal case ("a comment without an evidence link SHALL NOT be posted") has nothing to satisfy it |
| 9 | Agent-loop verdict contract (9) | `PASS`/`CHANGES_REQUESTED` verdict, exit code, `--fail-on` | **not shipped** | No promote/halt contract, no subject-digest keying, no re-entry as unverified. README points agents at an upstream `skills/stitcher-codereview/SKILL.md`, which is not vendored |

Counts, stated plainly: **6 present (5 fully, 2 partially), 2 absent (pre-commit
file, agent-loop contract), 1 partial-and-weak (task traceability), 0 wired, 0
tested in-tree, 0 behind the evidence contract.**

## The fixtures

`acceptance.md` requires Fixtures A–H per stage. **None exists.** The vendored
subset carries `package.json` scripts for them upstream (`test: vitest run`,
`mutate`, `bench`, `smoke`), but `test/`, `scripts/` and `bench/` were not
vendored — the file set is `action.yml`, `package.json`,
`package-lock.json`, `tsconfig.json`, `src/`. So Fixture A (orphan commit and
orphan task), C (reverse drift), D (SARIF round-trip), E (local/CI divergence),
F (comment without evidence), G (ingested identity) and H (loop
self-certification) all have no in-tree witness, and the action's behaviour in
this repo is asserted only by its README.

## Cross-cutting: the evidence contract the package makes a precondition

The package is explicit that "each promoted feature ships only behind the
evidence contract; feature completeness without evidence is not delivery". The
shipped contract today is `hub/coherence` — sealed evidence bundles
(`evidence.py`, `scripts/evidence-validate.py`), HMAC attestation (`attest.py`),
the coherence run ledger and scoped exceptions (`adoption.py`). The action
builds **its own** evidence shape in TypeScript (`src/evidence.ts`:
`RepoFingerprint{head, touchedHash, files, capturedAt}` + a `VerificationStatus`
vocabulary `ATTEMPTED…UNKNOWN` that deliberately refuses to let heuristic
findings claim `VERIFIED`/`TESTED`). That is a good design and it is not the
contract: no code path converts it to a coherence bundle, and no attestation is
produced. So every "present" row above is present *outside* the precondition
the package sets.

## A gate blind spot this read surfaced

`actions/` is not in `gate_common.DEFAULT_SOURCE_DIR_CANDIDATES`, so the size
gate never walks it — measured with the gate's own functions:

```
walk roots: ['lib', 'scripts', 'tools', 'openspec', 'hub', 'tests']
actions/  31 source files uncovered
engines/   4 source files uncovered
fleet-manager/ 26 source files uncovered
templates/ 1 source files uncovered
```

Those are the "4 scope gaps (warning)" in `regression_check.py --all`. The
consequence for this package: `src/serve.ts` is **558 lines** against a 500-line
hard limit and is invisible to the gate (0 over hard limit is true only of the
walked roots). This is precisely the class `check_scope_coverage` was built to
surface — it warns, and a warning is what it is — but a 5,739-line vendored
reviewer sitting outside the size gate, with no test and no CI wiring, is the
"green carries less proof" problem the package was written to reduce.

## What a future acceptance would have to decide

1. **Own or fork.** A vendored upstream at 0.4.1 with no tests is not a DevGate
   feature; either it is pinned and periodically re-vendored with its test
   suite, or the pieces DevGate wants are re-implemented against the shipped
   gates.
2. **Wire it or drop it.** No workflow, no consumer repo (`missioncontrol`,
   `MergeKingdom`, `agent-guardrails-template` checked) uses the action.
3. **Evidence adapter.** The one genuinely missing seam: `src/evidence.ts` →
   a coherence bundle + attestation, so a finding can be cited the way
   `coh-ev-*` requires.
4. **The three absent pieces** (pre-commit hook file, commit-keyed
   traceability, agent-loop contract) are new work in whichever repo owns the
   reviewer, not a vendoring step.
5. **Scope.** Add `actions` (and decide on `fleet-manager`, `engines`,
   `templates`) to `extra_source_dirs` if the code is to be first-party scope;
   leave it as a warning if it is deliberately out.

**Precedence:** the shipped ladder wins. No requirement id in this package is
wired to any code, traceability id or gate configuration (unchanged from the
import note in `proposal.md`), and this record does not create that wiring.
