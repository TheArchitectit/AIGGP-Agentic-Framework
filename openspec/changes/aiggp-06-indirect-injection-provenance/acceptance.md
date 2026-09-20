## Required conformance fixtures

- Fixture A: self-vouching content - class unchanged by claims.
- Fixture B: substituted chain link - verifier rejects, names break.
- Fixture C: third-party-justified destructive action - blocked under policy.
- Fixture D: uninstrumented ingestion path - unverifiable class, gap logged.
- Fixture E: derived content ancestry - full reconstruction from ledger.

## Release acceptance criteria

- All fixtures pass; envelopes with broken chains rejected; ancestry reconstruction demonstrated on a real mediated action; coverage audit published.

## Open questions requiring owner decisions

- Which ingestion paths are in scope for v1 (proposal: web fetch, email, tool results, non-repo file reads).
- Whether authorized class-raising exists at launch or lands post-launch (proposal: post-launch; keep v1 strictly monotonic).

## Handoff

Instrument the web-fetch and tool-result paths first - they are the highest-volume indirect-injection vectors. The demo that sells this spec: replay an attack that succeeded without provenance, then show the same attack classed, blocked, and reconstructed from the ledger.
