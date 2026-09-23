# Contributing

## Rules (machine-enforced where possible)

1. **Tests required.** A fix without a test that fails on the current tree
   is unverified. A new gate without a negative control is a rubber stamp.
2. **No vacuous green.** A suite that reports 0 tests, a scan that scanned
   nothing, a check that was skipped — these are FAILURES, not passes.
   Floors: `tests/expected-counts.json` (CI asserts them).
3. **Overlay, not fork.** Project customization goes through
   `.guardrails/` overlays. Baseline edits are maintainer-only.
4. **Scope contract is data.** Directory exclusions live in
   `.guardrails/scope.json` — never re-declare them in a gate script
   (`tests/test_scope_contract.py` enforces this).
5. **Shebang implies 100755 in the index.** `scripts/check_exec_bits.py`
   runs in CI; `core.fileMode=false` makes your local stat lie.
6. **Evidence in the PR.** Before/after test output, or a link to the CI
   run. Claims map to locks: `docs/threat-model.md` pattern.

## Security paths

`hub/coherence/**` and `scripts/deploy.sh` changes need a security review
(see MAINTAINERS.md). Include the threat-model row your change affects.

## Process

Write → Audit → Review → Merge (see AGENTS.md for the full discipline).
Small PRs. One remediation item per PR where feasible.
