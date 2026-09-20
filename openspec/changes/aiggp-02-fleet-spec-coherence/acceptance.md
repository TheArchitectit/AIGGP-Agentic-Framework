## Required conformance fixtures

- Fixture A: coherent minimal repository - full green.
- Fixture B: identity drift repo (gamerepo01 case) - FAIL naming drifted requirements.
- Fixture C: advisory-debt repo (LobsterWars case) - advisory stage with recorded debt, no block.
- Fixture D: repository bypass attempt (skipping assertions) - ERROR, not green.
- Fixture E: nondeterministic evaluator - conformance rejection.
- Fixture F: evidence tamper - verifier rejection with named check.
- Fixture G: 3D repair loop - verdict on new digest only.

## Release acceptance criteria

- All fixtures pass; determinism proven in CI; envelopes validate against AIGGP-00; one real fleet repo reaches Stage 2 with ledger history; one 3D promote/halt cycle completes end to end.

## Open questions requiring owner decisions

- Which fleet repos enter Stage 0 first, and the per-stage time bounds.
- Where the central policy minimums live before policy-bundles repo exists.

## Handoff

Reuse the September 17 package's component design verbatim where possible; the delta is envelope plumbing, the ladder's ledger record, and fixtures. Do not let any consumer special-case the verdicts - the contract is the product.
