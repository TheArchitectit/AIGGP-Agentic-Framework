# OAP Evidence Mapping v1

> Proposed only. This file maps existing DevGate semantics; it does not add a
> new top-level decision enum and does not make OAP an AIGGP authority.

## Direction and artifact identity

The adapter uses a separate transport/metadata envelope around the existing
DevGate canonical result. The canonical result remains unchanged and continues
to use `devgate.spec-coherence.result/v1` with decisions `PASS`, `ADVISORY`,
`FAIL`, and `ERROR` and exit codes `0`, `10`, `20`, `30–33`, and `40`.

The envelope adds, outside canonical decision bytes:

- `contract_version`: `devgate.oap-evidence/v1`;
- `direction`: `devgate-to-oap` or `oap-to-devgate`;
- `producer`: product, version, instance/key ID;
- `consumer_audience` and direction-specific operation scope;
- `tenant_or_project_id` and `subject_kind`/`subject_id`;
- `request_id`, `evaluation_id`, and idempotency key;
- canonical result digest, evidence-manifest digest, detached-attestation
  reference, policy/context/evaluator digests, and created/expiry bounds;
- `native_status` and `native_reason` from the producer;
- redaction/retention class and bounded evidence references.

Unknown critical fields, unsupported major versions, missing binding fields,
invalid digests, expired/revoked attestation, or cross-tenant context mismatch
are `ERROR`/non-PASS and cannot authorize promotion or OAP effects.

## Status mapping

| Producer state | DevGate canonical result | Required consumer meaning |
|---|---|---|
| PASS / all required assertions satisfied | PASS / exit 0 | May be considered only under receiving policy and exact binding |
| ADVISORY or exception-advisory | ADVISORY / exit 10 | Never mandatory PASS unless current policy explicitly allows advisory |
| FAIL / blocking violation | FAIL / exit 20 | Non-PASS; preserve findings and evidence |
| EMPTY, SKIP, UNKNOWN, INCONCLUSIVE | ERROR / exit 32 with native status metadata | Non-PASS; absence cannot authorize |
| malformed, unsupported, missing mandatory evidence | ERROR / exit 30/31/33/40 as applicable | Non-PASS; do not guess mapping |
| replay | Preserve canonical decision with `semantics=replay` | Non-promotion-authorizing unless freshly re-evaluated and re-attested |

The adapter never maps `ERROR`, `SKIP`, `UNKNOWN`, `INCONCLUSIVE`, or
`ADVISORY` to mandatory PASS. OAP may apply a stricter local decision, but it
cannot strengthen the producer claim.

## Replay and current authorization

Replay is reproduction only. To use historical evidence for a current OAP
operation, OAP must independently authorize the current principal/tenant/action,
check current policy/epoch/revocation and retention, and obtain a fresh
current-authority attestation or fresh evaluation. A producer timestamp is not
proof that a revoked artifact existed before revocation.

## Evidence integration

OAP evidence is carried as a bounded external evidence reference or a new
namespaced evidence object whose digest enters the existing evidence manifest.
It is not inserted into canonical decision bytes and cannot mutate the detached
attestation. Raw prompts, secrets, and unrelated source are not transported.

## Capability restrictions

Adapter credentials may read/submit the declared envelope only. They cannot
mutate policy, signer sets, exceptions, required checks, adoption stage, roles,
credentials, or OAP operations. Transport authentication and artifact
verification are separate claims and separate test cases.
