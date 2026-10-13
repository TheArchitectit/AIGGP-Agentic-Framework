# Cross-Product Evidence Auth v1 — Peer-Side Contract

> Proposed only. This is the shared method both sides implement. It adds no
> authority to AIGGP and does not change the canonical DevGate schemas.

## Identities and keys

- Each product instance has a workload identity and an Ed25519 key pair.
- Key ID = domain-separated SHA-256 over a version tag plus the canonical public
  key bytes. A key ID is public metadata, never a credential.
- Producers sign; consumers verify against keys provisioned out of band. A
  consumer never trusts a key learned from the artifact it is verifying.
- Keys carry issue/expiry and revocation state. Rotation uses an overlap window
  in which both old and new keys verify; revocation ends the window.

## Two independent claims

Transport authentication and artifact integrity are separate:

- **Transport:** mTLS with per-direction client certificates where a service
  connection exists; otherwise an audience-bound, short-lived signed request
  token. Transport identity is never reused as artifact signer identity.
- **Artifact:** every exchanged object carries a detached Ed25519 signature over
  canonical envelope bytes (sorted keys, UTF-8, no duplicate keys).

Shared HMAC remains acceptable only inside one trust domain and MUST be labeled
as shared-secret integrity with verifier forging power disclosed. It is never
described as non-repudiation and never used for cross-organization trust.

## Envelope (both directions)

Required fields: `contract_version`, `direction`
(`devgate-to-oap` | `oap-to-devgate` | `guardrails-to-peer` | `peer-to-guardrails`),
`producer_id`, `producer_key_id`, `consumer_audience`, `tenant_or_project_id`,
`subject_kind`, `subject_digest`, `policy_digest`, `context_digest`,
`evaluator_digest`, `request_id`, `evaluation_id`, `idempotency_key`, `nonce`,
`issued_at`, `expires_at`, `native_status`, `native_reason`, `payload_digest`,
`evidence_refs`, `signature`.

Unknown critical fields, unsupported major versions, missing bindings, or a
digest mismatch are non-PASS.

## Verification stages (in order)

1. **Shape/version:** supported `contract_version`, all required fields present.
2. **Transport:** authenticated peer identity and audience.
3. **Integrity:** recompute digests; verify signature against a currently valid,
   non-revoked key for that audience.
4. **Authorization:** the receiving product independently decides whether the
   evidence is required and whether the operation is permitted. Evidence never
   grants permission.

Each stage reports a distinct reason code. No stage's failure may be smoothed
into a later stage's success.

## Replay, freshness, revocation

- Unique `request_id`/`evaluation_id`; `idempotency_key` bound to subject plus
  payload digest.
- Reject expired, replayed, or duplicate side-effecting submissions.
- Replay reproduces a decision; it is non-promotion-authorizing unless freshly
  re-evaluated and re-attested under current authority.
- Revocation list is distributed with a maximum propagation bound. Offline
  bundles embed a revocation snapshot; a snapshot past its freshness bound is
  non-PASS. A producer timestamp is never proof of pre-revocation issuance.

## Least privilege

Adapter credentials are read/submit only and audience-scoped. They cannot
mutate policy, signer sets, roles, grants, tenants, credentials, exceptions,
required checks, adoption stage, or effects. A DevGate decision never authorizes
an OAP effect.

## Migration note

Legacy static keys (for example a shared `MCP_API_KEY` or an HMAC signer) MUST be
registered to an explicit principal and scope before cross-product use. During
migration they may be trusted only for the narrow surface they actually covered;
they never inherit broader authority by being present.
