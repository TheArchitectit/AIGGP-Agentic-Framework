# Tasks: Add OAP Evidence Consumer Contract

> **UNSHIPPED PROPOSAL.** This change is not shipped and promotes nothing. The
> only consumer implemented for it is a **non-authorizing local observer**
> (`hub/coherence/oap_observer.py`, `NON_AUTHORIZING = True`) — no OAP service,
> no receiver, no effect authority. Nothing below implies production promotion or
> that AIGGP is an identity issuer or effect authority. Checkmarks mean "grounded
> by the cited evidence", not "shipped".

## Gate 0 — Preconditions

- [ ] 0.1 Confirm OAP native authority/effect package has passed its own
  source-backed readiness gate for the pilot action. — **NOT_RUN — no OAP
  boundary exists in this repository.**
- [x] 0.2 Confirm AIGGP canonical decision/evidence/attestation schemas and
  status precedence are unchanged and verified at the target main commit. —
  **EXERCISED (local).** Existing canonical schemas are hash-frozen and asserted
  unchanged in `tests/test_oap_evidence_signature.py:104-111,866-873`
  (`result.schema.json`, `attestation.schema.json`).
- [ ] 0.3 Select one exact OAP consumer operation and one DevGate subject; record
  owners, policy/profile, evaluator, freshness, outage, and rollback. —
  **NOT_EXERCISED — no OAP consumer operation exists to select.**

## Gate 1 — Contract

- [ ] 1.1 Adopt and validate `mapping.md` against the existing result,
  request, evidence-manifest, attestation, identity, and context schemas; add
  the versioned envelope only after those checks pass. — **PROPOSED**
  (`mapping.md` written; not validated against a real OAP consumer).
- [ ] 1.2 Define optional OAP→DevGate evidence assertion with producer identity,
  native status, evidence reference, and exact request/subject binding. —
  **PROPOSED** (shape defined in `secure-method.md`; not exercised against OAP).
- [x] 1.3 Reject status strengthening: ERROR/SKIP/UNKNOWN/ADVISORY/FAIL cannot
  become mandatory PASS; replay is non-promotion-authorizing by default. —
  **EXERCISED (local).** PASS/0 paired with a non-PASS native status is rejected
  before canonicalization (`hub/coherence/strict_parse.py:246-250`) and again at
  the observer (`hub/coherence/oap_observer.py:118-119`); fixtures/negatives in
  `tests/test_oap_evidence_schema.py:63-77,275-284` and
  `tests/test_oap_v2_conformance.py:187-190`.
- [ ] 1.4 Define tenant/audience/direction authorization fields without making
  AIGGP an identity issuer or effect authority. — **WIRED partial.** Tenant /
  audience / direction binding fields exist and are enforced
  (`hub/coherence/strict_parse.py:297-299`, `hub/coherence/trust_store.py:204-245`)
  but no OAP-side authorization consumer exists to complete the contract.
- [x] 1.5 Define artifact bounds, redaction, expiry, idempotency, duplicate,
  revocation, unsupported-version, and unknown-critical-field behavior. —
  **EXERCISED (local).** Bounds `hub/coherence/strict_parse.py:41-43,119-145`;
  expiry/lifetime `:230-243`; unknown-critical-field/version
  `:202-228,284-296`; duplicate-key `:110-116`; idempotency/duplicate/revocation
  `hub/coherence/replay_guard.py:134-215`. Negatives in
  `tests/test_oap_evidence_schema.py:229-303` and
  `tests/test_oap_replay_guard.py:108-127`.

## Gate 2 — Conformance

- [x] 2.1 Add golden valid/invalid JSON fixtures and canonical mapping tests. —
  **EXERCISED (local).** Add-change fixtures
  (`openspec/changes/add-oap-evidence-consumer/fixtures/`) checked by
  `tests/test_oap_evidence_schema.py:53-86`; the v2 golden corpus
  (`openspec/changes/harden-oap-evidence-verification/fixtures/`, valid +
  duplicates/noncanonical/oversized/version/direction/missing-field/status-exit/
  expired) exercised by `tests/test_oap_evidence_schema.py:173-303`.
- [x] 2.2 Add wrong tenant/subject/policy/evaluator, tamper, replay, expiry,
  revoked signer, missing evidence, malformed schema, and status-laundering
  negative controls. — **EXERCISED (local).**
  `tests/test_oap_evidence_schema.py:59-86,193-303` and
  `tests/test_oap_v2_conformance.py:164-227`.
- [ ] 2.3 Prove local/CI/artifact adapter parity against the actual DevGate
  producer and verifier. — **WIRED partial.** Local producer→parser→verifier→
  observer parity is exercised (`tests/test_oap_v2_conformance.py:49-266`); the
  CI-lane and artifact-adapter halves against an OAP consumer are absent.
- [ ] 2.4 Preserve external producer identity; never relabel OAP or Guardrails
  results as native DevGate findings. — **WIRED partial.** Producer identity is
  carried on the envelope and bound to the signing key
  (`hub/coherence/oap_v2_producer.py:38-45`,
  `hub/coherence/trust_store.py:226-231`); no OAP producer exists to prove the
  no-relabel property.
- [x] 2.5 Test that the adapter has no policy, role, signer, exception, stage,
  or required-check mutation capability. — **EXERCISED (local).**
  `tests/test_oap_evidence_signature.py:848-864` (`TestBoundedSliceSurface`:
  closed public API, no I/O or policy-mutation imports, no policy-grant verbs);
  `hub/coherence/oap_evidence.py` `__all__`.

## Gate 3 — Observe-only pilot

- [ ] 3.1 Run one real producer→artifact→verifier→consumer path with no
  promotion or OAP-effect authority. — **PARTIAL — local only.** Bounded local
  loopback exercised (`tests/test_oap_v2_conformance.py:156-266`); no real OAP
  consumer, so the "one real path" is not run.
- [ ] 3.2 Record unavailable/unexercised producer paths as explicit non-PASS;
  never fabricate Guardrails/OAP evidence. — **Maintained.** Unavailable paths
  are recorded NOT_RUN / NOT_EXERCISED throughout these tasks and in
  `openspec/changes/harden-oap-evidence-verification/evidence-t134-mutation-and-spec-validation.md`.
- [ ] 3.3 Compare pinned local/CI results and publish limitations/retention. —
  **NOT_RUN — no CI/consumer comparison lane exists.**
- [ ] 3.4 Obtain independent review before any mandatory use. —
  **NOT_EXERCISED — no independent review obtained.**

## Explicitly deferred

- [ ] No network API, sidecar, webhook, admin UI, required check, or central
  policy service until real operational need and owner approval.
