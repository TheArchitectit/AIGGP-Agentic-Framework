# Change: Harden OAP Evidence Verification Before Any Mandatory Use

> **Status:** Proposed remediation specification only. No remediation is implemented by this package. `add-oap-evidence-consumer` remains proposed; no OAP integration or OAP effect authority is shipped by this change.

## Why

At the audited revision `e4fee8c`, the pure-Python Ed25519 verifier admits an identity public key and identity R with S=0 for arbitrary messages, and accepts noncanonical point encodings (`hub/coherence/ed25519.py:76-85,118-132`). A mathematically successful verification is therefore not an authenticity claim. The envelope path also lacks required independent time, payload, trust, status, and authorization checks (`hub/coherence/oap_evidence.py:156-241`). Existing tests establish RFC vectors and selected tamper failures, not these adversarial cases (`tests/test_oap_evidence_signature.py:63-88,136-315`).

## Outcome and scope

- Immediately quarantine the affected signature verifier and any artifacts depending on it as **non-authorizing**, including observe-only outputs that otherwise look like PASS. Deny mandatory promotion/effect use until independent remediation and conformance review succeed. No downgrade to unsigned, HMAC, replay, exception, or stale cached PASS.
- Specify the single proposed `devgate.oap-evidence/v2` signed wire format in `contract-v2.md`, closed boundary validation, independent context and signer trust, exact payload/result/manifest/attestation binding, replay protection, and faithful status mapping. Both incompatible v1 forms remain non-authorizing.
- Define implementation tasks and negative controls as future work; do not edit code, tests, schemas, current change package, or canonical DevGate contracts in this package.

## Exclusions

No OAP grant, identity issuer, effect engine, new network service, retired AIGGP kernel/CA/runner, or production enablement. Native OAP authority remains an independent prerequisite (`openspec/changes/add-oap-evidence-consumer/proposal.md:35-50`).

## Dependencies and release gate

Quarantine precedes all other work. Owner decision on cryptographic provider and runtime constraints precedes signing deployment. Wire-format freeze precedes parser/signer changes. Trust and semantic checks precede end-to-end conformance. An independent reviewer and the OAP owner must explicitly approve one exact receiving operation before optional observe-only use can be considered for mandatory gating; a green unit suite alone is insufficient.

## Source-backed audit map

- Crypto and key identity: `hub/coherence/ed25519.py:76-85,118-132`; `hub/coherence/oap_evidence.py:65-73,225-240`.
- Canonicalization and parse gap: `hub/coherence/canon.py:29-61`; `hub/coherence/oap_evidence.py:76-90`.
- Nested-versus-flat v1 shapes: `openspec/changes/add-oap-evidence-consumer/schemas/oap-evidence-envelope.schema.json:8-31,55-105`; `hub/coherence/oap_evidence.py:13-18,38-48`; `openspec/changes/add-oap-evidence-consumer/secure-method.md:30-54`.
- Semantic gaps: `hub/coherence/oap_evidence.py:156-241`; `hub/coherence/schemacheck.py:30-33,80-157`; `tests/test_oap_evidence_schema.py:55-69`.
- Existing canonical status/evidence rules: `openspec/specs/decision-contract/spec.md:11-27,59-75`; `openspec/specs/evidence-and-attestation/spec.md:11-45,71-87`.
- CI gates to restore/recheck: `.github/workflows/ci.yml:59-62,246-285,158-244`; `tests/test_oap_evidence_signature.py:51-60,308-315`.
