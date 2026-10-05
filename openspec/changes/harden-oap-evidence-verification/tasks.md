# Tasks: Harden OAP Evidence Verification

All tasks are unimplemented specification work. Gates are ordered; no later gate upgrades an earlier failed gate.

## Sprint summary

| Sprint | Gate | Focus | Effort | Priority | Depends on |
|--------|------|-------|--------|----------|------------|
| S-E0 | Gate 0 | Quarantine unsafe evidence path | S | P0 | — |
| S-E1 | Gate 1 | Crypto provider and wire contract | L | P0 | S-E0 |
| S-E2 | Gate 2 | Trust roots and semantic verification | L | P0 | S-E1 |
| S-E3 | Gate 3 | Producer-to-receiver conformance and CI | M | P0 | S-E0–S-E2 |

**Global stop rule:** No gate is complete without its exit criteria and named evidence. A failed, blocked, or stopped gate freezes all later gates. Do not reclassify a failure as skipped or waived to proceed. Later gates never upgrade an earlier failed gate.

## Gate 0 — Quarantine (blocking)

**Sprint:** S-E0 | **Effort:** S | **Priority:** P0
**Entry criteria:** Unsafe evidence verification is live in production/test/CI; no quarantine or inventory exists.
**Exit criteria:** All callers and accepted evidence inventoried with named owner; mandatory/promotion/effect use of unsafe-path evidence disabled and returning explicit non-authorizing status; rollback/re-enrollment and re-verification plan published.
**Dependencies:** None (first gate; must complete before S-E1–S-E3).
**Stop conditions:** Any production mandatory/promotion/effect still accepts unsafe-path evidence → stop and keep quarantine. Unsigned/HMAC fallback, stale-cache acceptance, exception, or legacy-key bypass introduced → reject and stop. Inventory cannot name a responsible owner for every caller → stop until owners are assigned.

- [ ] 0.1 Inventory all production/test/CI callers of `hub/coherence/ed25519.py` and `hub/coherence/oap_evidence.py`, artifact consumers, and already accepted evidence at the affected revision; document scope and responsible owner.
- [ ] 0.2 Disable mandatory/promotion/effect use of evidence verified by the unsafe path; return explicit non-authorizing status. Do not replace this with unsigned/HMAC fallback, stale-cache acceptance, exception, or legacy-key bypass.
- [ ] 0.3 Publish rollback/reenrollment and re-verification plan for previous artifacts; only trusted fresh reevaluation after remediation can restore authority.

## Gate 1 — Crypto and wire decisions

**Sprint:** S-E1 | **Effort:** L | **Priority:** P0
**Entry criteria:** S-E0 exit criteria met (quarantine active, inventory and rollback plan published).
**Exit criteria:** Vetted constant-time provider vs stdlib-only decision recorded with provenance, runtime, profile, and independent review; adversarial negative vectors and RFC/interop positives pass; `contract-v2.md` shape, 64-hex key ID, domain separation, strict parser, and independent Go receiver frozen with golden vectors; raw JSON parser pinned with resource bounds and pre-canonicalization rejects.
**Dependencies:** S-E0 (quarantine must remain in force during crypto work).
**Stop conditions:** Provider selected only on RFC happy-path vectors → stop. Independent Go receiver cannot be built or golden vectors not reviewed → stop before freezing the contract. Duplicate-key, unknown-critical-field, or invalid UTF-8 not rejected → stop before declaring parser complete. Either incompatible v1 shape translated on receipt → stop.

- [ ] 1.1 Security and runtime owners choose vetted constant-time signing provider versus stdlib-only constraint; record package provenance, supported runtime, verification profile, and independent review. Reject a decision based only on passing RFC happy-path vectors.
- [ ] 1.2 Add adversarial tests: identity A `01` + 31 zero bytes with identity R and S=0 on multiple unrelated messages MUST fail; noncanonical y (including y >= p), low-order A/R, malformed/sign-bit encodings, S>=L, wrong message/key MUST fail; valid RFC vectors and independent-provider interop MUST pass.
- [ ] 1.3 Implement the proposed `contract-v2.md` body/signature shape, full 64-hex key ID, domain-separated signed bytes, strict parser, and independent Go receiver; review golden vectors before freezing. Reject both incompatible v1 shapes rather than translating on receipt. Any change to these fields requires a new reviewed contract version.
- [ ] 1.4 Pin strict raw JSON parser and resource bounds; reject nested duplicate keys, unknown critical fields, invalid UTF-8, unsupported version, and invalid schema keywords/semantics before canonicalization.

## Gate 2 — Trust and semantic verification

**Sprint:** S-E2 | **Effort:** L | **Priority:** P0
**Entry criteria:** S-E1 exit criteria met (contract frozen, vetted verifier and strict parser in place).
**Exit criteria:** Authenticated time windows and max-age/skew/key windows enforced with negative tests; signer roots/revocation snapshots provisioned outside artifact and untrusted caller input; payload/result/manifest/attestation digests and cross-links verified; independently derived authorization and status/exit precedence enforced; durable atomic replay/idempotency and explicit non-authorizing offline mode in place.
**Dependencies:** S-E1 (frozen contract and vetted verifier).
**Stop conditions:** Trust material sourced from the artifact or untrusted caller input → stop. Valid signature over lying digests accepted → stop. Offline mode grants authority → stop. Replay/idempotency not durable across restart/concurrency/retry-after-expiry → stop.

- [ ] 2.1 Require authenticated current time, `issued_at`/`expires_at`, max age/skew/key windows; test future, expired, inverted, timezone-naive, absent-time, and stale-revocation cases.
- [ ] 2.2 Provision signer roots/registrations and authenticated revocation snapshots outside artifact and untrusted caller input; bind producer, key, tenant, direction, audience, operation; test malicious caller keyring/snapshot, revoked/rotated keys and cross-scope signing.
- [ ] 2.3 Require real payload and result/manifest/attestation bytes; recompute digests, verify detached attestation and all cross-links. Test omitted payload, missing or swapped evidence, changed manifest/result/attestation, valid signature over lying digests, and unavailable remote refs.
- [ ] 2.4 Enforce independently derived tenant/subject/package/policy/context/evaluator/image/producer/direction authorization, strict status/exit precedence, replay semantics, and signer-side field validation. Test each wrong identity, malformed fields, PASS/0 plus native ERROR, and other non-PASS combinations.
- [ ] 2.5 Provide durable, atomic replay/idempotency handling for each effect-bearing receiver and explicit non-authorizing offline mode; test repeated nonce/request/evaluation, same idempotency key with altered bytes, concurrency, restart, and retry after expiry.

## Gate 3 — Producer-to-receiver conformance and CI

**Sprint:** S-E3 | **Effort:** M | **Priority:** P0
**Entry criteria:** S-E0–S-E2 exit criteria met; positive and every Gate 1–2 negative fixture available.
**Exit criteria:** End-to-end DevGate producer → v2 bounded raw artifact → strict parser → vetted verifier → independently provisioned trust store → Go OAP observe-only consumer exercised with all negatives; cross-language canonical-byte/signature vectors and mandatory-check inventory frozen; CI green on final remediation revision (reconciled schema pins, `openspec validate --all --strict`, pinned secret scan) and mutation tests kill reintroduced identity-key and duplicate-key acceptance; independent security reviewer and OAP owner approve one named operation before any mandatory promotion/OAP effect.
**Dependencies:** S-E0, S-E1, S-E2.
**Stop conditions:** Mocked copy of acceptance logic or fixture-only PASS used as evidence → stop. Schema pins auto-updated or secrets suppressed to force CI green → stop. Mutation tests do not kill reintroduced unsafe acceptance → stop. Independent reviewer or OAP owner withholds approval → remain observe-only and keep quarantine non-authorizing.

- [ ] 3.1 Exercise actual DevGate producer→v2 bounded raw artifact→strict parser→vetted verifier→independently provisioned trust store→Go OAP observe-only consumer, with positive and every Gate 1–2 negative fixture. Freeze cross-language canonical-byte/signature vectors and an expected mandatory-check inventory; no mocked copy of acceptance logic or fixture-only PASS.
- [ ] 3.2 Restore CI health and document evidence: reconcile pinned schema hashes deliberately (`tests/test_oap_evidence_signature.py:51-60,308-315`), run `openspec validate --all --strict` with the native `## ADDED Requirements` delta grammar, and rerun the pinned secret scan (`.github/workflows/ci.yml:158-285`). Record latest known failures as failures until reruns are green; never suppress or auto-update pins just to pass.
- [ ] 3.3 Run focused tests, strict spec validation, traceability, and secret scan on the final remediation revision; ensure tests kill an intentionally reintroduced identity-key acceptance and duplicate-key acceptance.
- [ ] 3.4 Independent security reviewer and OAP owner assess full producer→receiver evidence and one named operation; approve separately before any mandatory promotion/OAP effect. Otherwise keep observe-only and quarantine non-authorizing.
