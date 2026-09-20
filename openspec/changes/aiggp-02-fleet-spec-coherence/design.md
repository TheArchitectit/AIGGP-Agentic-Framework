## Design principles

- Determinism or it did not happen: same revision, same spec package, same policy, same verdict.
- Advisory before enforced: trust is earned per repo, ratcheted, and cannot regress silently.
- Underlying truth is preserved: advisory findings are recorded with full fidelity even when they do not block.
- One promote/halt contract across code and 3D artifacts.

## Locked decisions (carried from the September 17 package, re-anchored to AIGGP)

- Container reference runtime: pinned, ephemeral, default-deny network, least-privilege secrets, bounded execution.
- All decision inputs identified by content digest: repo revision, spec package, policy package, evaluator image.
- Canonical result contract plus a noncanonical run envelope; now defined as the AIGGP-00 evidence envelope.
- Assertion model: every normative spec requirement maps to at least one assertion; orphan requirements fail coherence.
- Policy minimums live outside repositories; repos may tighten but never loosen centrally set minimums.
- Exceptions are scoped, bounded, and expiring; wildcard exceptions are invalid.
- Result states map onto the AIGGP algebra: PASS, FAIL, SKIP (reason-coded), ERROR, EMPTY (never green).

## Major components (as designed September 17, unchanged in shape)

1. Invocation adapter (CI, CLI, pipeline calls).
2. Subject resolver (repo at pinned revision).
3. OpenSpec resolver (pinned, immutable package; moving references rejected).
4. Policy resolver (stage-appropriate minimums).
5. Assertion planner and evaluator runtime (isolated, no repo writes).
6. Decision engine (stage-aware verdict).
7. Evidence store adapter - now writing AIGGP envelopes to the ledger.
8. Attestation emitter - now the AIGGP envelope signature chain.

## Trust boundaries

- Repository boundary: the evaluator reads; it never writes.
- Container boundary: default-deny network, ephemeral filesystem.
- Plugin boundary: assertion plugins are untrusted; crashes are ERROR, not SKIP.
- Control-plane boundary: fleet systems distribute and observe; they do not reinterpret verdicts.
