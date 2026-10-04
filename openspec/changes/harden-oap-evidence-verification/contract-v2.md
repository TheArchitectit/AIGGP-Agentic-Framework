# Cross-product evidence contract v2 — proposed freeze

**Status:** Proposed target for implementation, not a shipped wire protocol.
`devgate.oap-evidence/v1` currently names two incompatible shapes; neither is
accepted for mandatory use. The current pure-Python Ed25519 verifier accepts a
low-order-key forgery and remains non-authorizing. An executor must not repair
this by relabeling an old v1 artifact as v2.

## 1. First slice and authority

The first consumer is Go OpenAgentPlatform, receiving one DevGate coherence
result for an exact repository revision, **observe-only**. The OAP instance
provisions expected tenant/project, subject, required checks, policy/context,
allowed producer and signer independently; none comes from the artifact as
authority. The reverse direction and Guardrails producers require separate
producer-native payload schemas and an exercised consumer before activation.
A valid receipt never permits an OAP effect. DevGate remains the owner of its
canonical result and detached attestation; OAP owns action authorization.

## 2. Single wire shape

The UTF-8 JSON wire object has exactly two top-level members:

- `body`: one canonical JSON object containing the fields below; no unknown
  fields, floating-point values, duplicate keys, or `null` in required fields.
- `signature`: detached object `{ "algorithm": "Ed25519", "key_id":
  "ed25519:...", "value": "ed25519:..." }`. It is not inside `body`.

`body` contains exactly:

| Field | Type / meaning |
|---|---|
| `contract_version` | literal `devgate.oap-evidence/v2` |
| `direction` | literal `devgate-to-oap` for the first slice |
| `producer_id`, `consumer_audience`, `tenant_or_project_id` | nonempty bounded identifiers; compared to independently provisioned expected context |
| `subject_kind`, `subject_digest` | exact candidate kind and `sha256:` digest; repository revision is an input identity, not authority |
| `request_id`, `evaluation_id`, `nonce`, `idempotency_key` | nonempty bounded opaque identifiers; receiving authority binds replay scope |
| `issued_at`, `expires_at` | UTC RFC3339 seconds (`YYYY-MM-DDTHH:MM:SSZ`); maximum lifetime 5 minutes for the first pilot; no future issuance beyond 30 seconds of trusted receiver time |
| `policy_digest`, `context_digest`, `evaluator_digest` | `sha256:` + 64 lowercase hex; compare to expected context |
| `native_decision`, `native_exit_code`, `semantics` | DevGate's canonical `PASS/ADVISORY/FAIL/ERROR`, matching 0/10/20/30–33/40 and `fresh-promotion` or `replay` |
| `native_status`, `native_reason` | attributed native producer status and bounded reason; never a second authority |
| `result_digest`, `evidence_manifest_digest`, `attestation_digest` | digests of separately supplied exact bytes; all three required |
| `payload_digest` | digest of the bounded DevGate payload bytes carried separately; required even for an empty payload |
| `observe_only` | literal `true` in the first slice; an enforced version needs a new approved contract |

All identifiers are ≤256 UTF-8 bytes, `native_reason` ≤512 bytes, and the
entire wire object ≤64 KiB. Evidence/result/attestation inputs have separate
approved size caps and are never accepted merely because their digest strings
are signed. The receiving authority supplies the expected required-check ID
set: a producer-supplied list cannot make a missing check disappear.

## 3. Canonical bytes and signature

Parse raw UTF-8 bytes with duplicate-key rejection at **every** object depth
and resource limits before canonicalization. Serialize `body` using the
DevGate restricted canonical JSON profile (`hub/coherence/canon.py`): sorted
object keys, compact separators, UTF-8 JSON with its existing escaping rule,
int64-only numbers, no floats, and no unknown fields. The exact signed input is
ASCII `devgate.oap-evidence/v2` followed by one zero byte followed by the
canonical `body` bytes. The signature never covers a lossy projection of a
larger object. Freeze cross-language golden byte/signature vectors for Unicode,
key order, escapes, int64 boundaries, duplicate keys, unknown keys, and line
endings before implementing a second producer or verifier.

Public keys are exactly 32 raw bytes. Key IDs are `ed25519:` followed by **all
64 lowercase hex characters** of SHA-256 over ASCII
`devgate.oap-evidence.key-id/v2`, one zero byte, and the public key bytes.
Signatures are `ed25519:` followed by 128 lowercase hex characters encoding
64 raw bytes. v1's truncated key IDs and flat signed-field subset are not
v2-compatible. A receiving trust record binds producer ID, key ID, public key,
tenant/project, audience, direction, permitted operation, validity window and
revocation version. Provisioning is out of band; the artifact cannot add keys.

Production signing must use an owner-approved vetted constant-time provider;
the current pure-Python signer is not permitted to hold production private
keys. Verification must reject low-order/noncanonical public keys and R,
identity points, invalid sign bits and S ≥ L. This is a cryptographic release
gate, not a claim that v2 cryptography is already safe.

## 4. Receiver validation (all required, in order)

1. Bound raw bytes and depth; reject invalid UTF-8, duplicates, unsupported
   version/direction, unknown fields and invalid types.
2. Load current authenticated expected context and trusted receiver time;
   require known signer, key ID/public-key match, producer/tenant/audience/
   direction/operation grant and fresh revocation state. Caller-supplied
   keyrings/clocks are test fixtures only, never production authority.
3. Verify v2 signature over the exact canonical bytes and enforce issuance,
   expiry, key validity, revocation and lifetime. A claimed pre-revocation
   `issued_at` cannot override current revocation.
4. Require supplied bounded payload, canonical result, evidence manifest and
   detached attestation bytes. Recompute all declared digests; validate their
   native schemas and internal cross-bindings in sealing order. Missing bytes
   or inaccessible refs are non-PASS, not optional.
5. Compare every signed tenant/subject/policy/context/evaluator/producer field
   to the independently approved context; compare native status, decision,
   exit code and the receiver's expected required-check set. `PASS/0` paired
   with any non-PASS native status or incomplete assertion set is ERROR.
   `ADVISORY` remains ADVISORY even if a receiving policy separately permits
   an advisory workflow; it is never rewritten to mandatory PASS.
6. Atomically claim replay/idempotency scope in receiver-owned durable state
   before a side effect. Exact retry may return its recorded **non-authorizing**
   outcome; changed bytes with the same key, duplicate nonce, stale snapshot,
   expired envelope or replay semantics deny. Offline verification without
   fresh authenticated revocation and durable replay state is observe-only.
7. Apply OAP's current native principal/tenant/action/resource decision at the
   protected effect boundary. A verified evidence artifact cannot override a
   local denial or supply missing OAP identity/grants.

Each failure has a stable distinct reason class, redacted audit entry and no
protected effect. Transport authentication (mTLS or an explicitly reviewed
short-lived audience-bound workload token) and artifact verification are
separate tests. Artifact-only local/CI exchange does not imply a network API.

## 5. Required fixture and rollout gate

A single v2 golden fixture must be produced by the real DevGate producer,
serialized to raw bytes, parsed by an independent Go OAP verifier, checked
against independently provisioned trust/context, and consumed observe-only.
Mutation fixtures must fail for low-order and noncanonical Ed25519 points,
duplicate keys at both levels, nested-vs-flat v1 input, wrong signer/tenant/
subject/policy/context/evaluator, missing or substituted bytes, status/exit
laundering, replay, expiry, stale revocation, concurrent duplicate admission
and OAP native denial. CI records exact commit, run ID and whether the tests
actually executed. The v2 contract is not accepted until both product owners
review the fixture corpus and the current crypto implementation is safe.
