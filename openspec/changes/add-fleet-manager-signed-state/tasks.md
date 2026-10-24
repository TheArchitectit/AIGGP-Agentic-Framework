# Tasks: add-fleet-manager-signed-state

Program package: `devgate-product-tiers-fleet-manager`, Sprint 3 box 3.3
(failure and revocation fixtures; two test hosts reconcile signed no-op desired
state — FLEET-006). Predecessors: `add-fleet-manager-agent-channel` (3.1),
`add-fleet-manager-agent-operations` (3.2).

## 1. The envelope

- [x] 1.1 `SignedState` — audience, revision, sequence, issued/expires,
      canonical body text, signature; signature and body kept out of `repr`
- [x] 1.2 The body must be canonical JSON text of a desired-state document;
      the three refusals are distinct (not JSON / not canonical / not a
      desired-state document)
- [x] 1.3 The signature is 64 bytes of lowercase hex; the lifetime is bounded
      by `MAX_STATE_LIFETIME`
- [x] 1.4 `signed_bytes()` — one frozen profile covering every field but the
      signature, pinned byte for byte by a test
- [x] 1.5 `state_to_document()` / `state_from_document()` — closed wire form:
      a missing field is named, an unknown field is refused, the declared schema
      is required

## 2. Audience

- [x] 2.1 One audience per envelope, a valid host identifier
- [x] 2.2 `accept_state()` refuses another audience, and the audience check runs
      before the lifetime and the signature

## 3. Replay and freshness

- [x] 3.1 `StateIssuer` allocates a strictly increasing sequence per audience;
      `last_sequence()` reports it, and is `None` for an audience never served
- [x] 3.2 The issuer builds the unsigned value first and signs exactly
      `signed_bytes()` of the value it returns
- [x] 3.3 `accept_state()` refuses a sequence that is not greater than the last
      accepted one, and accepts a gap
- [x] 3.4 Expiry and clock skew are judged against the supplied instant; the
      module never reads the wall clock
- [x] 3.5 Acceptance is a pure check and advances nothing
- [x] 3.6 A signer or verifier that raises is a refusal with no fallback; only
      exactly `True` verifies

## 4. The two-host world

- [x] 4.1 `fixtures/two-hosts/world.json` — two enrolled hosts, one pool, one
      warm runner each, already converged, with hand-written expectations
- [x] 4.2 `fixtures/two-hosts/cases.json` — thirteen failure and revocation
      cases, each naming the rule and the message fragment that names it; no
      signature material in the fixtures
- [x] 4.3 `tests/test_two_hosts_v1.py` — the Sprint 3 exit as a test: both hosts
      enroll, sign a report, are accepted, verify their own signed no-op state,
      and reconcile it to no drifts and no changes
- [x] 4.4 A healthy host's accepted report becomes work, and a revoked host's
      report does not — the pair, so the refusal cannot be vacuous
- [x] 4.5 A forgery is refused before the replay state advances, so the genuine
      report that follows is still accepted

## 5. Evidence

- [x] 5.1 `tests/test_state_v1.py` — 40 tests, floor-pinned
- [x] 5.2 Structural tests: the module imports no way to execute a process and
      never reads the wall clock
- [x] 5.3 Planted mutations against `state.py`
- [x] 5.4 `docs/qa/2026-10-24-fleet-manager-signed-state.md` — mutation table,
      gate table, and what is deliberately absent
