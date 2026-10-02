## Required conformance fixtures

- Fixture A: self-vouching content - class unchanged by claims.
- Fixture B: substituted chain link - verifier rejects, names break.
- Fixture C: third-party-justified destructive action - blocked under policy.
- Fixture D: uninstrumented ingestion path - unverifiable class, gap logged.
- Fixture E: derived content ancestry - full reconstruction from ledger.

## Release acceptance criteria

- All fixtures pass; envelopes with broken chains rejected; ancestry reconstruction demonstrated on a real mediated action; coverage audit published.

## Open questions requiring owner decisions

### Q10.1 — Which ingestion paths are in scope for v1

**ANSWERED 2026-10-01 (owner).**

**All four in v1: web fetch, email, tool results, non-repo file reads.**
The proposal's own definition of indirect injection is incomplete without
any of them; a partial-coverage v1 undercuts the demo's legitimacy
("replay an attack that succeeded without provenance, then show the same
attack classed, blocked, and reconstructed from the ledger"). The
handoff's "start with web-fetch and tool-result paths first" is a
*build-order* note (highest-volume vectors first within the v1
contract), not a scope reduction — it sequences the provenance-rig
implementation so the highest-volume vectors are fixture-covered first,
while all four paths are in the v1 release-acceptance criteria.

### Q10.2 — Whether authorized class-raising exists at launch or post-launch

**ANSWERED 2026-10-01 (owner).**

**Post-launch as proposed; v1 is strictly monotonic.** The v1 invariant:
once a piece of content is classed, its class stays. Class-raising
(retroactive re-scoring when a benign-looking page is later confirmed
hostile) would break monotonicity — it rewrites what an evidence
envelope records as truth at fetch-time, exactly the
travels-fleet-wide-on-flip class from the aiggp-00 Q1
org-wide-blast-radius rule. Retroactive reclass is a post-launch
opt-in feature, gated behind an integrity-preserving design (raised
class is a *new* envelope referencing the old, not a mutation of it),
and a schema-version bump on the provenance-conflict resolution field
when it ships.

## Handoff

Instrument the web-fetch and tool-result paths first - they are the highest-volume indirect-injection vectors. The demo that sells this spec: replay an attack that succeeded without provenance, then show the same attack classed, blocked, and reconstructed from the ledger.
