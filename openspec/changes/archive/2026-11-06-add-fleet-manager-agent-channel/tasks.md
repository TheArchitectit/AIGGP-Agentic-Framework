# Tasks: add-fleet-manager-agent-channel

Program package: `devgate-product-tiers-fleet-manager`, Sprint 3 box 3.1
(outbound host-agent channel — FLEET-004). Predecessors:
`add-fleet-manager-domain-models` (2.1), `add-fleet-manager-plan-apply` (2.2),
`add-fleet-manager-reconciliation-fixtures` (2.3).

## 1. Enrollment

- [x] 1.1 `AgentChannel.issue_token()` — a one-time token bound to one host and
      its pools, lifetime capped, id generated from the CSPRNG when not supplied
- [x] 1.2 `AgentChannel.enroll()` — the identity comes from the token, never
      from the request; a token is consumed once; expiry and pre-issuance are
      refused; the token value is never echoed
- [x] 1.3 `key_id_for()` derives the key id from the key; a key already enrolled
      to another host is refused in both enrollment and rotation

## 2. Rotation and revocation

- [x] 2.1 `rotate()` — new active generation, old credential `RETIRING` for a
      bounded overlap; refuses the same key, a revoked credential, and a key
      enrolled elsewhere
- [x] 2.2 `revoke()` — immediate, applies to a retiring key, refuses a second
      revocation, and never frees the key for re-enrollment
- [x] 2.3 Absolute credential lifetime (`not_after`) is enforced separately from
      the rotation overlap

## 3. Signed reports

- [x] 3.1 `signed_bytes()` — one frozen canonical profile (sorted keys, compact,
      UTF-8, no NaN), pinned byte for byte; `body_json` must already be that
      canonical text so the signed bytes and the consumed body cannot disagree
- [x] 3.2 `accept()` — credential, freshness, signature through the injected
      provider, sequence, nonce; a raising provider is a refusal and there is no
      fallback; a truthy non-bool is refused
- [x] 3.3 Replay state is committed only after verification, so a forged report
      cannot burn a sequence number

## 4. Replay protection

- [x] 4.1 Strictly increasing sequence per (host, key); gaps accepted
- [x] 4.2 Nonce unique per (host, key), retention bounded by the envelope expiry
- [x] 4.3 Message lifetime capped at 300s; freshness judged against a supplied
      instant with a 60s skew allowance; nothing reads the wall clock

## 5. Evidence

- [x] 5.1 `tests/test_channel_v1.py` — 51 tests, floor-pinned to this module
- [x] 5.2 A structural test that parses `channel.py` and fails on any network
      import or wall-clock read (FLEET-004 as a property of the code)
- [x] 5.3 `docs/qa/2026-10-24-fleet-manager-agent-channel.md` — the planted
      mutations, the gate table, and what is deliberately absent
