## Required conformance fixtures (per stage, minimum set)

- Fixture A: orphan commit and orphan task - both reported.
- Fixture B: undeclared change - flagged, no clean verdict.
- Fixture C: silent behavior change - reverse-drift finding.
- Fixture D: SARIF round-trip - schema valid, renders in viewer.
- Fixture E: local/CI divergence seed - parity harness catches.
- Fixture F: comment without evidence link - refused.
- Fixture G: ingested external result - identity preserved.
- Fixture H: loop self-certification - treated as unverified.

## Release acceptance criteria

- Each stage's fixtures pass before the next begins; every promoted feature emits valid envelopes on its real path; the promoted set is reported with per-feature maturity.

## Open questions requiring owner decisions

- Whether the unmerged parity branch (07aadb05, delivered as a Drive bundle) is applied first and reconciled, or re-implemented stage by stage (proposal: reconcile first, then stage gates).
- First external-tool adapter target (proposal: the highest-signal scanner already in fleet use).

## Handoff

Reconcile the existing parity branch against current main first (same cherry-pick discipline as AIGGP-01), then run the stages in order. Every stage demo shows the negative control failing first - that is the proof the feature is real.
