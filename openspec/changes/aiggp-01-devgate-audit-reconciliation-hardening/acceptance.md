> **Re-anchored 2026-10-02:** `aiggp-00`/`aiggp-09` are retired (see `openspec/changes/AIGGP-RETIREMENT-2026-10-02.md`); references below read against DevGate's shipped evidence machinery (`hub/coherence/`) and runner enrollment (`scripts/runner-enroll.sh`).

## Required conformance fixtures

- Fixture A: unscanned diff attempt - must fail.
- Fixture B: zero-test repo - must fail EMPTY.
- Fixture C: wrong-tree deploy - must fail on the project's unaudited change.
- Fixture D: dead-rule config - startup must fail naming rules.
- Fixture E: contaminated baseline - validation must fail naming entries.
- Fixture F: HIGH runtime vulnerability - must block absent waiver.
- Fixture G: path traversal content - must be contained and reported.

## Release acceptance criteria

- All fixtures pass on current main at a named commit; identical local/CI runs; finding ledger shows every item closed or waived with expiry; corpus runs in CI as blocking.

## Open questions requiring owner decisions

### Q3.1 — pre-existing guardrails_scan pytest failures on main: fix here or track separately

**CLOSED MOOT 2026-10-01.**

Measured at HEAD (`devgate/secret-gate-adoption`):
- `pytest tests/test_guardrails_scan_node.py` → **3/3 passed**
- `node tests/test_guardrails_scan.mjs` → **23/23 passed**

Zero failures on the surface the question names. Either the failures were
fixed in an intervening commit or the wording was always stale — either way
there is no defect to fix or track. Keeping the question open would treat a
green surface as a finding. If a future regression returns, it enters the
finding ledger as it lands, not as a reopened open question.

(Measurement record: same sweep that caught the `test_ratchet_demo.py`
pre-archive-path red, fixed in this tree. 1315 passed, 1 failed → 1316
passed after the anchor repoint; the ratchet red was caused by my own
archive commit `a74455a`, not this package's subject.)

### Q3.2 — Kit + Ryan audit branch: delete after cherry-pick reconciliation or archive

**ANSWERED 2026-10-01 (owner).**

**Action: A.** Cherry-pick the raw Kit + Ryan audit digests from
`origin/chore/external-audit` into `docs/qa/audit-digest/` on main
*first*, then preserve the pre-cherry-pick branch tip as an annotated
git tag and delete the branch ref. Rationale measured on this date:

- The branch holds 9 commits unique vs main, all Roger-authored
  `external-audit(digest): YYYY-MM-DD findings` and each touching exactly
  one of `docs/qa/audit-digest/{2026-09-19,21,22,25,26,27,28}.md`.
- **None of those files exist on main.** Cherry-pick-by-finding in the
  design.md sense applies each finding's *fix* (fixture + commit) to
  main, but never carries the auditors' raw prose with it. Deleting the
  branch without first preserving those 7 files is a one-way door on the
  raw audit trail — the exact class the org-wide-blast-radius invariant
  (aiggp-00 Q1) names.

Thus the branch is **not deleted until the digest prose is in main's
history**, at which point the branch ref is redundant. The tag
(`kit-ryan-audit-2026-09-28`) preserves the pre-cherry-pick tip as a
read-only reference forever; the active branch ref is safe to drop.

If any future branch-disposal decision runs into the same "raw evidence
only lives on a stale branch" shape, reuse the same two-step: (1) land
the raw content at its canonical path, (2) tag-then-delete.

## Handoff

Start with the finding ledger; it is the work plan. Do not bulk-merge the audit branch. Every fix lands with a failing-then-passing fixture pair, and the corpus becomes permanent CI - the fixtures are attack cases, not documentation.
