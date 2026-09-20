## Required conformance fixtures

- Fixture A: valid bundle, valid envelopes, passing aggregation - full green path.
- Fixture B: zero-discovery run - must not pass.
- Fixture C: expired waiver over a FAIL - must remain FAIL.
- Fixture D: tampered envelope - must be rejected with named check.
- Fixture E: tampered ledger - verifier names the chain break.
- Fixture F: nondeterministic bundle source (embedded timestamp) - build must fail or normalize deterministically.

## Release acceptance criteria

- All fixtures pass on the kernel; both shadow adapters emit valid fixtures; verifier runs offline; document regeneration is byte-identical.

## Open questions requiring owner decisions

- Signature algorithm and key custody for envelope signing (per-install keys vs org keys).
- Ledger storage backend for local-first installs (file vs embedded database).

## Handoff

Build the schema library and fixtures first; nothing else in AIGGP should block on full verifier polish. The conformance kit is the public face of the kernel: treat its clarity as a launch feature, not an afterthought.
