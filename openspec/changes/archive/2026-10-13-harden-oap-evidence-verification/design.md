# Design: Quarantine, Freeze, Verify, Then Consider Adoption

## 0. Immediate quarantine

The unsafe verifier is not a trust boundary: `hub/coherence/ed25519.py:76-85` does not reject noncanonical y or low-order points, and `:118-132` accepts identity A, identity R, S=0. Mark every output relying on this path **non-authorizing**; block its use in required checks, releases, OAP effects, or promotion. Inventory consumers and previously accepted evidence; reverify or reevaluate under the remediated verifier and current policy rather than grandfathering. Expose explicit rejection/hold reason; do not silently turn PASS into authorization. Maintain quarantine until every later gate passes.

## 1. Cryptographic implementation decision (owner review)

Preferred production option: maintained, vetted Ed25519 provider with constant-time private-key signing, canonical encodings, scalar range and subgroup/low-order rejection compatible with the selected RFC 8032 verification profile. Pin dependency/version, review license, packaging, supported platforms, side-channel properties, and authoritative negative vectors. The current stdlib-only contract (`hub/coherence/ed25519.py:2-17`) conflicts with relying on such a provider: security owner and runtime owner must explicitly resolve this before adopting one. If stdlib-only is retained, require independent cryptographic review and adversarial interoperability testing; Python scalar signing is not constant-time and MUST NOT be exposed as a timing-sensitive signer. Merely patching the identity point does not close this design gate. Document the precise verification profile, including canonical A/R, subgroup handling, S<L, and non-malleability; reject identity and other low-order public keys even when a provider accepts them.

## 1a. Solo-maintainer cryptography decision

For the first production-capable slice, private-key signing SHALL use a vetted,
maintained constant-time Ed25519 provider with pinned dependency/provenance and
independently reviewed key custody. The existing pure-Python module may remain
as an educational/test-vector implementation but SHALL NOT sign with a
production key or qualify as the mandatory verifier until strict low-order,
noncanonical, malleability and cross-provider vectors pass. If packaging cannot
supply the vetted provider, the integration stays observe-only/non-authorizing
rather than falling back to the unsafe verifier or HMAC. AIGGP's existing HMAC
coherence attestations retain their current shared-secret integrity meaning;
they do not become cross-product issuer attribution or OAP permission.

The chosen v2 wire and testable receiver order are in `contract-v2.md`.
An incompatible nested or flat v1 artifact is rejected, not silently migrated
on receipt. The first slice is DevGate→Go OAP for one synthetic, observe-only
script-dispatch subject. A reverse adapter is conditional on a second real
consumer and a separate producer-native schema. No central service or private
key is added to the UCS03 runner for this planning milestone.

## 2. One wire format and parse boundary

Freeze a versioned signed wire object; the nested artifact schema (`openspec/changes/add-oap-evidence-consumer/schemas/oap-evidence-envelope.schema.json:8-31,67-105`) and flat signed fields (`hub/coherence/oap_evidence.py:38-48`) MUST NOT both claim `devgate.oap-evidence/v1` until one representation and a lossless, testable mapping are approved. Choose whether signature is detached from the outer nested object or covers an explicitly defined flat projection; bind every security-relevant field (including observe-only scope, operation, producer, exact result/manifest/attestation refs), reject unmapped critical fields, and assign a new version for incompatible changes. Do not change frozen canonical DevGate result/attestation bytes to repair transport. Reject duplicate keys at every JSON object depth **before** `json.loads` can erase them; cap input bytes, depth, and collections; decode UTF-8 strictly; reject unknown critical fields and unsupported versions. Canonicalization of an already-parsed dict (`hub/coherence/canon.py:29-61`) cannot detect original duplicates. Schema checking is necessary but not sufficient: test keyword coverage (including date-time and semantic relations) rather than assuming `hub/coherence/schemacheck.py:80-157` enforces the entire contract.

## 3. Mandatory validation order

For each candidate, fail closed with a reason at the first failed gate while retaining an auditable, non-secret error class:

1. Parse raw bytes, reject duplicates, bound resources, apply the single frozen schema and signed-field coverage rules. Signing also rejects invalid/unknown/empty fields and incoherent status/scope before issuing a signature (`hub/coherence/oap_evidence.py:76-110` currently checks presence and key ID only).
2. Obtain trusted receiver identity, operation, direction, tenant/project, subject, policy/context, evaluator/image, producer registry, allowed signer set, and current UTC time from the receiving authority **independently of the artifact**. A caller may not supply an arbitrary keyring, revocation snapshot, clock, or expected context as an authority substitute. A controlled test may inject an authenticated clock/trust fixture only in test scope.
3. Check signer validity and revocation from authenticated, fresh trust state (bounded offline snapshot with authenticated origin, version, timestamp, and freshness limit; stale/unavailable state denies). Check key ID binding, producer→key→tenant/audience/direction/operation authorization, and signature. Cryptographic validity alone is not authorization. No producer timestamp can exempt an already revoked key.
4. Enforce `issued_at <= now < expires_at`, max lifetime/skew policy, strict timezone-aware timestamp parsing, key-window overlap, and request-specific freshness. Omitting a reference time or a payload is not an acceptance mode (`hub/coherence/oap_evidence.py:206-223,231-235`).
5. Fetch bounded, authorized evidence bytes; recompute exact payload, canonical result, evidence-manifest, and detached-attestation digests; validate each object's schema and cross-bind result identities/decision, manifest, attestation statement and signer. Never trust a digest or reference simply because it was signed. Missing, inaccessible, redacted-beyond-verification, or mismatched required bytes deny mandatory use. Preserve canonical sealing order (`openspec/specs/evidence-and-attestation/spec.md:11-45,71-87`).
6. Compare all signed identities and native status/exit semantics to trusted expected context and actual producer output. PASS/0 is incompatible with ERROR/FAIL/ADVISORY/SKIP/UNKNOWN/INCONCLUSIVE; replay is never fresh PASS. Receiving authority independently decides whether verified evidence is relevant; OAP alone grants effects.
7. Atomically record replay/idempotency scope over trusted tenant, audience, direction, operation, request/evaluation IDs, nonce, subject, and payload digest before any side effect. Exact retry may return the prior non-authorizing outcome; altered content with a reused key and expired/replayed submissions deny. Offline verification without trusted replay state is non-authorizing.

## 4. Deployment and rollback

Begin with negative fixtures and independently generated positive vectors, then controlled observe-only producer→artifact→receiver exercise. Record reason codes and source revision, never raw secrets. Mandatory enablement requires explicit reviewer signoff, current OAP authority approval, green pinned CI gates and rollback to deny/observe-only on any regression; no self-approval via repository-provided evidence. The OAP consumer proposal remains a separate dependency, not an already deployed integration (`openspec/changes/add-oap-evidence-consumer/proposal.md:3-25,35-50`).
