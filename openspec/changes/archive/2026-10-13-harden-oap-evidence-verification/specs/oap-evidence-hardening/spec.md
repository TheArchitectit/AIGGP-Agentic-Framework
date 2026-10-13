# OAP Evidence Hardening

## ADDED Requirements

### Requirement: Unsafe verifier evidence is non-authorizing until remediation
<!-- id: coh-oap-hard-01 -->
Evidence verified using the affected pure-Python Ed25519 path MUST NOT satisfy a mandatory check, promotion, release, or OAP effect. The receiving authority MUST quarantine affected artifacts, explicitly deny or hold authorization, and MUST NOT substitute unsigned, stale, replayed, HMAC, or exception evidence. Restoration requires fresh verification or reevaluation under independently reviewed remediation and current policy.

#### Scenario: identity-point forgery during quarantine
- **WHEN** identity public key `01` followed by 31 zero bytes and identity R with S=0 are offered as a signature for any message
- **THEN** the artifact is non-authorizing regardless of a legacy verifier's reported result

### Requirement: Reviewed cryptographic verification profile
<!-- id: coh-oap-hard-02 -->
The signing and verification implementation MUST use an owner-approved cryptographic provider and a documented Ed25519 profile that rejects low-order and noncanonical public keys and R encodings, invalid sign bits, malformed lengths, and S outside the canonical scalar range. Private-key signing in a timing-sensitive environment MUST use a vetted constant-time implementation. The stdlib-only runtime constraint MUST be resolved by security and runtime owners before production signing; a stdlib-only alternative requires independent cryptographic review and MUST NOT claim constant-time safety without proof.

#### Scenario: mathematically degenerate signature
- **WHEN** a verifier receives identity A, identity R, S=0 for two distinct messages, or a noncanonical y encoding
- **THEN** verification rejects each case rather than treating the group equation alone as authenticity

### Requirement: One closed signed wire contract
<!-- id: coh-oap-hard-03 -->
A producer and consumer MUST agree on exactly one versioned signed representation and canonicalization profile covering every security-relevant envelope field. Incompatible nested and flat shapes MUST NOT share an ambiguous v1 identity; migration requires an explicit version and refusal of unmappable artifacts. The receiver MUST reject duplicate JSON keys at any depth from raw bytes before parse/canonicalization, invalid encoding, unknown critical fields, oversized artifacts, unsupported versions, and schema/semantic violations. The signer MUST reject invalid, absent, unknown, or incoherent binding fields rather than sign them.

#### Scenario: duplicate key erased by parsing
- **WHEN** a raw envelope contains two `tenant_or_project_id` keys or repeated nested identity keys
- **THEN** parsing rejects the entire artifact before either value can be signed or verified

#### Scenario: competing v1 shapes
- **WHEN** a nested v1 document is supplied to a flat v1 signer or verifier without an approved lossless mapping
- **THEN** signing or verification fails instead of silently dropping unsigned fields

### Requirement: Independently provisioned signer and context trust
<!-- id: coh-oap-hard-04 -->
The receiver MUST obtain current signer registration, revocation state, trusted time, and expected tenant, subject, package, policy, context, evaluator/image, producer, direction, audience, and operation from an authenticated authority independent of the artifact and untrusted caller. Signer registration MUST authorize its key for the exact producer, tenant, direction, audience, and operation; an arbitrary caller-supplied keyring or revocation snapshot is not trust. Offline snapshots MUST be authenticated and fresh within an approved bound; stale or unavailable trust denies mandatory use. Signature success never grants an OAP effect.

#### Scenario: attacker provisions their own key
- **WHEN** an attacker signs a well-formed artifact and supplies its key in a caller-owned keyring or stale non-revoked snapshot
- **THEN** the receiver denies it against its independently provisioned current trust state

#### Scenario: valid signature for another scope
- **WHEN** an authorized key signs evidence for the wrong tenant, subject, policy, evaluator, producer, direction, audience, or operation
- **THEN** the receiving authority denies use for the requested context

### Requirement: Fresh and complete evidence binding
<!-- id: coh-oap-hard-05 -->
For authorizing consideration, the receiver MUST require a trusted current time and verify well-formed `issued_at` and `expires_at`, ordering, maximum lifetime/skew, key validity, and current revocation; omitting a time or payload MUST NOT create an acceptance path. The receiver MUST retrieve required bounded bytes and recompute payload, canonical result, evidence-manifest, and detached-attestation digests, verify their schemas, signature, identities, and cross-binding in sealing order. Missing, mismatched, inaccessible, or unverifiable evidence is non-PASS. A producer timestamp MUST NOT override current revocation.

#### Scenario: signed lie about evidence
- **WHEN** a correctly signed envelope names result, manifest, or attestation digests whose fetched bytes do not match, or the payload is absent
- **THEN** mandatory use is denied, even when the envelope signature itself verifies

#### Scenario: time not provided
- **WHEN** verification lacks an authenticated reference time or the envelope is expired, future-dated beyond skew, or signed by a revoked key
- **THEN** mandatory use is denied rather than skipping the time or key-window checks

### Requirement: Faithful status and replay semantics
<!-- id: coh-oap-hard-06 -->
The receiving authority MUST compare the producer's native status, canonical decision, exit code, assertion completion, and fresh/replay semantics before treating evidence as a candidate PASS. ERROR, FAIL, ADVISORY, SKIP, UNKNOWN, INCONCLUSIVE, malformed, incomplete, or replayed output MUST NOT be laundered into mandatory PASS/0. Effect-bearing submission MUST atomically enforce scoped nonce/request/evaluation and idempotency uniqueness over trusted tenant, direction, audience, operation, subject, and payload; altered retries, duplicates, expired submissions, or unavailable replay state are non-authorizing. A verified DevGate result is evidence, not OAP permission.

#### Scenario: status laundering
- **WHEN** a signed envelope claims native ERROR with canonical PASS/0 or a fresh PASS from replayed evidence
- **THEN** the consumer reports non-PASS and does not authorize promotion or an OAP effect

#### Scenario: duplicate side-effect request
- **WHEN** an already consumed idempotency key is resubmitted with altered payload or another evaluation ID
- **THEN** the receiver denies a new side effect; an exact retry may only retrieve its previously recorded non-authorizing outcome

### Requirement: End-to-end conformance before mandatory adoption
<!-- id: coh-oap-hard-07 -->
Mandatory enablement MUST remain blocked until a real producer→serialized artifact→raw parser→cryptographic verifier→independent trust store→receiver path proves valid and malicious cases, and independent security and OAP owners approve one exact operation. CI MUST run negative controls for degenerate Ed25519 points, duplicate keys, conflicting wire shapes, missing payload, status laundering, wrong binding, stale/revoked signer, expiry, and replay; it MUST also pass pinned schema-hash checks, strict OpenSpec validation, traceability, and secret scanning without bypasses. Observe-only fixtures or a unit-level signature PASS alone MUST NOT be claimed as OAP integration.

#### Scenario: CI or owner gate fails
- **WHEN** any conformance, pinned schema, strict OpenSpec, secret scan, or independent owner gate fails or has not run
- **THEN** the operation remains non-authorizing and the failed or missing gate is reported explicitly
