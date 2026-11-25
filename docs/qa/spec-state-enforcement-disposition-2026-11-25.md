# Spec-state enforcement placement disposition

- **Observed** 2026-11-25 19:31 UTC
- **Capability** `spec-state-ledger` / `spec-state-09`
- **Source** Unauthenticated public GitHub API
- **Review** Independently verified

## Classification

| Control | Observed placement | Classification |
|---|---|---|
| `scripts/hooks/pre-commit` spec-state block | Runs before local commit only when installed with `core.hooksPath=scripts/hooks`; it rejects an invalid staged state transition. `git commit --no-verify` bypasses it. | **Bypassable local prevention** |
| `.github/workflows/spec-state.yml` | Runs on `push` to `main` and audits `before..HEAD` when the earlier commit resolves. The fallback checks `HEAD^` or the root commit. | **After-the-fact detection** |
| GitHub branch protection for `main` | Public REST API reports `protected:false`, checks enforcement `off`, and no branch rules. Owner-only protection endpoint returned HTTP 401. | **Publicly reported unprotected; owner-only settings UNKNOWN/NOT_RUN** |

The push workflow does not prevent a direct push. If it finds a violation after the push, repair is a follow-up commit; it cannot undo or block the already-moved ref. The local hook offers a pre-commit block only in clones where it is installed and where its relevant trigger is reached.

## Evidence

- Workflow trigger: [trigger (line 16)](../../.github/workflows/spec-state.yml#L16). Range resolution and gate invocation: [range resolution (line 43)](../../.github/workflows/spec-state.yml#L43), [gate invocation (line 55)](../../.github/workflows/spec-state.yml#L55). It audits `before..HEAD` when the pushed `before` commit resolves; otherwise it falls back to `HEAD^`, or `HEAD` when there is no parent (lines 47-53). Exit 3 for a no-scan is rejected (lines 65-68). The workflow labels itself “detection, not prevention” at line 29 and reports failure after landing at line 70.
- Hook installation, bypass, and omissions: [installation instructions (line 29)](../../scripts/hooks/pre-commit#L29), [bypass note (line 195)](../../scripts/hooks/pre-commit#L195), and [missing-gate behavior (line 203)](../../scripts/hooks/pre-commit#L203). The staged trigger excludes deleted paths with `--diff-filter=ACMR` ([line 208](../../scripts/hooks/pre-commit#L208)).
- Disposable replay: the installed hook returned exit 1 for a staged spec-state change without a ledger row; that blocked attempt created no commit. The same staged state was then committed with `git commit --no-verify` as a new commit. `scripts/spec_state_gate.py --base <base> --head HEAD` returned exit 1 for that committed range. This confirms prevention is local and bypassable, while the workflow gate is detection after commit/push.
- Read-only GitHub API capture at **2026-11-25 19:31 UTC**, without credentials: branch endpoint HTTP 200 (`protected:false`, status-check enforcement `off`, head `cb96da16da4d59e102b68005a9094404a41a0c3f`); branch-rules endpoint HTTP 200 (`[]`); full protection endpoint HTTP 401 (`Requires authentication`). The last endpoint leaves owner-only configuration UNKNOWN/NOT_RUN.
- Strict OpenSpec validation passed **76/76**. Traceability reported **246/282** covered, with 36 advisory uncovered; `spec-state-09` remains uncovered and advisory. No source binding was invented.

The [DG-07 change evidence](../../openspec/changes/archive/2026-11-25-dg-07-spec-state-gate-enforcement/evidence.md) records commands, limitations, and check results.
