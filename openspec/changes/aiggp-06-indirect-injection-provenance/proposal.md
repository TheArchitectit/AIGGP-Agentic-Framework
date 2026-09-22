> **Status: imported draft — not a commitment.** The AIGGP program has not started; this package is imported reference material held for future acceptance. It does not modify, supersede, or bind the shipped DevGate specification ladder, and no code, traceability ID, or gate configuration is wired to its requirements. (Added 2026-09-20 per the spec-coherence drift audit; see the AIGGP-02 reconciliation.)

## Summary

Define content provenance as first-class evidence: an origin chain attached to every external content input an agent processes, verifiable through the AIGGP-00 envelope, with trust decisions derived from provenance class rather than content claims.

## Problem

Indirect injection works because content arrives context-free: the agent sees text, not where the text has been. A webpage's instruction, an email's "you already approved this," and a tool result's embedded commands all look identical to the model. Guardrails main has provenance concepts; the platform needs them mapped onto the evidence envelope so origin is verifiable, not asserted. Without this, AIGGP-03's classifier fights every battle with no intelligence about the source.

## Desired outcomes

- Every external content input carries a provenance record: origin identifier, retrieval path, timestamps, trust class, and transformations applied.
- Provenance classes are declared: owner-channel (authenticated user), first-party tool output, third-party content, anonymous/unverifiable. Trust derives from class, never from content's claims about itself.
- Content lacking provenance defaults to the lowest trust class.
- Downstream decisions inherit provenance: an action justified by third-party content is evidence-linked to that content's origin chain.
- Tampered or broken chains are detectable by the kernel verifier.

## Product boundary

This spec owns provenance structure, classes, and evidence mapping. Detection/decoding mechanics (parsing obfuscated payloads, classifying instruction-like content) remain AIGGP-03/04 runtime-module logic. It does not prevent injection by itself; it makes source-aware policy possible and source-blind decisions visible.

## Users and calling systems

- Guardrails runtime module attaching provenance at ingestion points (fetch, email, tool results, file reads outside the repo).
- AIGGP-03 mediation consulting provenance class for policy decisions.
- Kernel verifier validating chain integrity in envelopes.
- Auditors reconstructing why an agent trusted what it trusted.

## Success measures

- 100 percent of external content inputs at mediation boundaries carry provenance records or are classed anonymous/unverifiable.
- Verifier rejects envelopes with broken or substituted chains, naming the break.
- Policy can express "no destructive action justified solely by third-party content" and conformance proves it holds.
- Origin reconstruction: given any mediated action, its full content ancestry is recoverable from the ledger.

## Risks

- Provenance theater: records attached but never consulted. Control: conformance fixtures require policy decisions that differ by provenance class.
- Overhead at every ingestion point. Control: provenance is structural (who/where/when), not deep inspection; cheap to attach, expensive only to fake.
- Partial adoption leaves blind spots. Control: ingestion points are enumerated in the bundle; uninstrumented sources default to untrusted, which is visible.
