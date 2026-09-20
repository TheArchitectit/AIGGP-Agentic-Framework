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

- Whether pre-existing guardrails_scan pytest failures on main (untouched since before v1.1.0) get fixed in this package or tracked separately.
- Whether the Kit + Ryan audit branch is deleted after cherry-pick reconciliation or archived.

## Handoff

Start with the finding ledger; it is the work plan. Do not bulk-merge the audit branch. Every fix lands with a failing-then-passing fixture pair, and the corpus becomes permanent CI - the fixtures are attack cases, not documentation.
