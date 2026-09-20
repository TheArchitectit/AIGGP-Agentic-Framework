## Design principles

- Origin is fact, trust is policy: provenance records what happened; the bundle decides what it means.
- Content never vouches for itself: claims inside content cannot raise its class.
- Chains, not labels: each transformation appends; history is preserved.
- Lowest class by default: absence of provenance is itself a provenance fact.

## Locked decisions

- Provenance record fields: origin identifier, origin class, retrieval path, fetched-at, fetched-by (agent/tool identity), content digest, transformation list, parent references.
- Four trust classes: owner-channel, first-party, third-party, unverifiable. Classes are ordinal for policy.
- Inheritance: derived content (summaries, extracted text, tool outputs over fetched data) links parents; its class is the minimum of its parents unless an authorized transformation raises it (which is itself recorded).
- Envelope integration: mediation decisions reference the provenance chain digests of justifying content.
- Verification: chain integrity (digests, append-only transformations) is kernel-verifiable; class policy is bundle-defined.

## Major components

1. Provenance record schema (kernel envelope extension).
2. Ingestion instrumentors at fetch/email/tool/file boundaries.
3. Chain store linking content digests to records.
4. Policy hooks exposing class to mediation (AIGGP-03/04).
5. Verifier support for chain integrity.
6. Ancestry reconstructor for audit (ledger query).

## Trust boundaries

- Instrumentors are trusted to attach honest records; their outputs are digest-chained so later tampering is detectable.
- Third-party content is untrusted input even when well-formed; well-formedness affects parse, not class.
- Authorized class-raising transformations (for example a human explicitly vouching for a document) are recorded with the authorizing identity.
