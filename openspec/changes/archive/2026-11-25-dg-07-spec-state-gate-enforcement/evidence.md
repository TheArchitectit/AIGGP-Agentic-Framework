# DG-07 enforcement placement evidence

## Local behavior

- `.github/workflows/spec-state.yml:16-18` triggers only on pushes to `main`. Its range step audits `before..HEAD` when the pushed `before` commit resolves, otherwise falls back to `HEAD^`, or `HEAD` when no parent exists (`:43-53`). It runs `scripts/spec_state_gate.py --base ... --head HEAD` (`:55-60`). Exit 3 for a no-scan is rejected (`:65-68`), and other failures are surfaced after the push (`:69-72`). This is after-the-fact detection; it cannot block the ref update that triggered the run.
- `scripts/hooks/pre-commit:180-203,208-210,217-229` implements a local pre-commit block when installed. It inspects staged published spec/ledger paths and constructs a prospective commit for the gate. The hook is not auto-installed; its instructions name `git config core.hooksPath scripts/hooks` at lines 29-34. `git commit --no-verify` bypasses it, as documented at lines 195-197.
- Existing hook exclusions are preserved and stated: the staged path query uses `--diff-filter=ACMR` (`scripts/hooks/pre-commit:208`), so a pure delete is not selected by that hook trigger; and the spec-state block returns success when `scripts/spec_state_gate.py` is absent (`:200-203`). These limitations do not justify describing the hook as universal prevention.
- A disposable local Git replay copied the actual pre-commit hook and spec-state gate into an isolated fixture. Two unrelated earlier checks used passing fixture commands. The hook rejected a staged invalid state transition with exit 1 and a missing-ledger diagnostic. The blocked attempt produced no commit. The same staged state was then committed with `git commit --no-verify`. The range gate returned exit 1 with the same violation.
- The existing disposable negative-control harness passed all designed cases after normalizing its CRLF line endings in a temporary copy: positive control accepted; malformed transitions, missing marker/evidence, empty scan, bad revision, unknown field, status ratchet, and row deletion were rejected as designed. Direct Bash execution of the mounted PowerShell checkout FAILED before scan because Bash rejected the CRLF line endings (`set: pipefail` with a carriage return and a syntax error). The normalized disposable copy passed without changing the worktree.

## Remote state readback

The writer captured public, read-only GitHub REST API responses for
`TheArchitectit/AIGGP-Agentic-Framework` at **2026-11-25 19:31 UTC**.
Independent readback at **19:39 UTC** corroborated the results below.

- `GET /repos/TheArchitectit/AIGGP-Agentic-Framework/branches/main` — HTTP 200; `protected: false`; `protection.required_status_checks.enforcement_level: off`; observed branch head `cb96da16da4d59e102b68005a9094404a41a0c3f`.
- `GET /repos/TheArchitectit/AIGGP-Agentic-Framework/rules/branches/main` — HTTP 200; empty list (`[]`).
- `GET /repos/TheArchitectit/AIGGP-Agentic-Framework/branches/main/protection` — HTTP 401, `Requires authentication`.

The public readback reports `main` as unprotected and no branch rules. The complete owner-only protection settings and any settings not exposed by those public endpoints remain **UNKNOWN/NOT_RUN** because the owner-only endpoint required authentication. No claim is made that a push-time check prevents direct pushes.

## Validation and identity

- `/opt/toolchain/node_modules/.bin/openspec validate --all --strict` — **76 passed, 0 failed**.
- `python3 scripts/spec_traceability.py` — **246/282 requirements covered**, 36 advisory uncovered; exit 0. `spec-state-09` remains **UNCOVERED (mode=advisory)**. Its requirement ID is unchanged, and no enforcement source marker or canonical spec-state change was added.
- Pre-work `python scripts/regression_check.py --all` did not complete. In the mounted Windows worktree, Docker could not resolve the `.git` pointer to its `C:/...` host path. A retry using explicit Git directory metadata ran without producing a completed result and was stopped after more than three minutes; lead-owned final candidate gates remain pending.
- Independent review corroborated the local hook and pushed-range controls,
  public readback, and strict validation. Follow-up review verified the
  corrected source links, range fallback, and CRLF replay status.
