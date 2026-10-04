# Tasks: Add OAP Evidence Consumer Contract

## Gate 0 — Preconditions

- [ ] 0.1 Confirm OAP native authority/effect package has passed its own
  source-backed readiness gate for the pilot action.
- [ ] 0.2 Confirm AIGGP canonical decision/evidence/attestation schemas and
  status precedence are unchanged and verified at the target main commit.
- [ ] 0.3 Select one exact OAP consumer operation and one DevGate subject; record
  owners, policy/profile, evaluator, freshness, outage, and rollback.

## Gate 1 — Contract

- [ ] 1.1 Adopt and validate `mapping.md` against the existing result,
  request, evidence-manifest, attestation, identity, and context schemas; add
  the versioned envelope only after those checks pass.
- [ ] 1.2 Define optional OAP→DevGate evidence assertion with producer identity,
  native status, evidence reference, and exact request/subject binding.
- [ ] 1.3 Reject status strengthening: ERROR/SKIP/UNKNOWN/ADVISORY/FAIL cannot
  become mandatory PASS; replay is non-promotion-authorizing by default.
- [ ] 1.4 Define tenant/audience/direction authorization fields without making
  AIGGP an identity issuer or effect authority.
- [ ] 1.5 Define artifact bounds, redaction, expiry, idempotency, duplicate,
  revocation, unsupported-version, and unknown-critical-field behavior.

## Gate 2 — Conformance

- [ ] 2.1 Add golden valid/invalid JSON fixtures and canonical mapping tests.
- [ ] 2.2 Add wrong tenant/subject/policy/evaluator, tamper, replay, expiry,
  revoked signer, missing evidence, malformed schema, and status-laundering
  negative controls.
- [ ] 2.3 Prove local/CI/artifact adapter parity against the actual DevGate
  producer and verifier.
- [ ] 2.4 Preserve external producer identity; never relabel OAP or Guardrails
  results as native DevGate findings.
- [ ] 2.5 Test that the adapter has no policy, role, signer, exception, stage,
  or required-check mutation capability.

## Gate 3 — Observe-only pilot

- [ ] 3.1 Run one real producer→artifact→verifier→consumer path with no
  promotion or OAP-effect authority.
- [ ] 3.2 Record unavailable/unexercised producer paths as explicit non-PASS;
  never fabricate Guardrails/OAP evidence.
- [ ] 3.3 Compare pinned local/CI results and publish limitations/retention.
- [ ] 3.4 Obtain independent review before any mandatory use.

## Explicitly deferred

- [ ] No network API, sidecar, webhook, admin UI, required check, or central
  policy service until real operational need and owner approval.
