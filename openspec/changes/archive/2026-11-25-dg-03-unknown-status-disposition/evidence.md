# DG-03 disposition evidence

**Review date:** 2026-11-25

**Disposition source snapshot:** `4bc3f050c7178c8642fb38738b0a4328329c13d9` (detached worktree)

**Read-only ready-tree comparison:** `0921b11e5c8bf81a1f6231c7dc6d73c06b157402`

**Disposition artifact:** [`openspec/UNKNOWN-DISPOSITIONS.md`](../../../UNKNOWN-DISPOSITIONS.md)

## Roster and reconciliation

The original DG-03 design names 12 UNKNOWN capabilities. The isolated source snapshot index reports 64 canonical specs and 19 UNKNOWN (74 IDs), including seven later additions. A read-only roster check against ready commit `0921b11` found 65 canonical specs and 20 UNKNOWN (75 IDs); the added capability is `drift-workflow-setup-instructions` with `drift-setup-note-01`. Its table row is based on ready-tree source and archived DG-20 evidence.

To check normal post-archive lifecycle behavior, a disposable copy was assembled directly from ready commit `0921b11`, with only the three disposition documents copied in. OpenSpec 1.14.3 archived DG-03 there and created canonical `spec-status-disposition` with IDs `spec-state-10` and `spec-state-11`. After running `scripts/spec_index.py --write` in that disposable copy, the index reported 66 specs and 21 UNKNOWN; `scripts/spec_index.py --check` then passed. Strict OpenSpec 1.14.3 validation passed 75/75 in the archived disposable copy. The new capability has no closure table, explicit `Status:`, or ledger proof and is therefore UNKNOWN. Both new IDs are recorded as `insufficient`; the disposition does not self-certify closure. Byte comparisons confirmed the simulation did not change either ready-tree lifecycle ledger, and the isolated source and ledgers remain unchanged.

`game-type-phase-matrix` remains explicitly DEFERRED under owner answer `base-specs-01` and is not counted as UNKNOWN.

The entries name owner roles rather than inventing individual owners. Evidence pointers distinguish local source/tests from proof that was not supplied. Source markers and test existence are not treated as closure evidence. The dispositions are written separately from lifecycle status; neither `openspec/INDEX.md`, `openspec/state-ledger.jsonl`, nor `openspec/state-unproven.jsonl` was edited.

## Verification and limits

- `python3 scripts/spec_index.py --check`: passed on the isolated source snapshot and after index regeneration in the post-archive disposable copy (`spec-index: OK - INDEX.md matches the generator`).
- `npx --yes @fission-ai/openspec@1.14.3 validate --all --strict`: passed, 75 items.
- The formerly failing focused test was reproduced in a disposable Linux-local repository created from `git -c core.autocrlf=false -c core.eol=lf archive HEAD`, then initialized and committed locally with the three disposition documents copied as LF: `tests/test_gitlab_forge_support.py::test_glf11_and_glf12_runner_enrollment_and_digest_pin` passed (1 passed). The checkout had canonical LF bytes; no product code was changed.
- Required `python3 scripts/regression_check.py --all` passed in that disposable checkout: no potential regressions, 0 hard-limit findings, 0 scope gaps, and no package vulnerabilities. It reported pre-existing size warnings plus 81 added documentation lines skipped by the unscoped prose-pattern scan. This check compared the three current disposition documents against a tagged baseline commit in the disposable repository.
- The original mounted-worktree attempt remains recorded in the task history: the ordinary linked-worktree mount could not resolve the Windows `.git` file target; a retry with explicit Git environment hung on mounted Git operations and was stopped. The canonical-LF replay resolves the specific runner-enroll failure without changing product code.
- `git diff --check`: passed after edits.

External proof remains open for live fleet enrollment, GitLab instance/adoption/parity/restore, hosted policy enforcement, external consumer implementation, and human art acceptance. No requirement is claimed CLOSED by this review. The ready-tree roster was inspected read-only; the isolated worktree remains at its assigned baseline and its canonical `INDEX.md` and ledgers were not altered.
