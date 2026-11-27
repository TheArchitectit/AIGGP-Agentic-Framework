# Tasks

## 1. Agent channel

- [ ] 1.1 Qualify token binding, expiry, one-time redemption, key uniqueness, revocation and secret-safe refusals (`fleet-004-02`).
- [ ] 1.2 Qualify canonical signed bytes, malformed or forged reports, exact verifier results and provider failure; document the verifier and persistence boundaries (`fleet-004-03`).
- [ ] 1.3 Exercise replay, nonce reuse, sequence gaps, freshness and verification-before-state-update across the intended persistence boundary (`fleet-004-04`).
- [ ] 1.4 Exercise rotation overlap, expiration and immediate revocation including a retiring key (`fleet-004-05`).

## 2. Typed work and evidence

- [ ] 2.1 Inspect every parameter name before any parameter value. Refuse a forbidden name by name with the specified no-remote-shell diagnostic even when its value is malformed; test ordering and value non-disclosure (`fleet-005-01`).
- [ ] 2.2 Qualify default-deny capabilities, runtime presence, read-only operations and the separate cancellation policy grant (`fleet-005-02`).
- [ ] 2.3 Qualify credential-shaped value refusal, opaque registration references and bounded parameters and receipt details (`fleet-005-03`).
- [ ] 2.4 Qualify issued-key/host binding, evidence-bearing completion, idempotent retries and conflicting receipt refusal (`fleet-005-04`).
- [ ] 2.5 Verify authoritative receipt construction and schema mapping, read-only exclusion, and the runner-enrollment migration table (`fleet-005-05`).

## 3. Boundary and proof

- [ ] 3.1 Exercise undeclared files and forbidden changed roots, manifest/license failures, and open-core dependency direction through the CI gate (`repo-002-01`, `repo-002-02`, `repo-002-03`).
- [ ] 3.2 Establish reviewable source and test provenance for rows 121-132, assess existing QA records, and bind accepted historical claims to independently validated requirement-specific evidence bundles and expected digests before submitting any transition.
