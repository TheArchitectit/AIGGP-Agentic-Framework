# Acceptance

## Required conformance fixtures

### Fixture A: coherent minimal repository

A small repository whose approved package, source behavior, manifest, and primary documentation agree. Expected result: PASS with no findings.

### Fixture B: gamerepo01 identity drift

A synthetic snapshot representing the verified failure class: primary documents or artifact metadata describe different game identities or lineages. Expected result: the stable product-identity assertion is VIOLATED with exact evidence locations. The fixture must not depend on private narrative inference at runtime.

### Fixture C: LobsterWars advisory debt

A baseline with 13 named advisory violations. Expected results:

- Stage 1: ADVISORY, all 13 visible;
- Stage 2 unchanged: ADVISORY for named baseline debt;
- Stage 2 with a new finding: FAIL;
- expired baseline exception: FAIL;
- broad wildcard exception: invalid policy.

### Fixture D: repository bypass attempt

A local overlay removes a centrally required assertion or chooses an unapproved evaluator. Expected result: invalid policy or FAIL, never PASS.

### Fixture E: nondeterministic evaluator

An evaluator reads current time, unordered filesystem results, or live network state. Expected result: denied capability or ERROR. Repeated runs must not produce inconsistent passes.

### Fixture F: evidence tamper

A finding evidence file changes after bundle sealing. Expected result: digest or attestation verification fails.

### Fixture G: 3D repair loop

An original scene bundle fails, a bounded repair creates a new digest, and the repaired bundle passes after full reevaluation. Expected result: the original attestation cannot promote the repaired subject; the new PASS binds the repaired digest.

## Release acceptance criteria

The first production release is acceptable only when:

1. All normative schemas are versioned and published with compatibility tests.
2. The canonical replay suite passes 100 consecutive runs per supported architecture.
3. Every required assertion appears exactly once in complete result accounting.
4. Required skips, unresolved checks, evaluator errors, and evidence errors block in enforced mode.
5. Local policy cannot weaken central policy in adversarial tests.
6. The container passes non-root, read-only, capability, host-socket, resource, secret-redaction, and default-deny-egress tests.
7. Signed attestation verification detects any bound digest substitution.
8. The adoption ladder enforces advisory expiry and Stage 2 no-regression behavior.
9. CI, local, and fleet adapters produce equivalent canonical results for the same inputs.
10. The `gamerepo01`, LobsterWars, bypass, nondeterminism, tamper, and 3D fixtures produce their expected decisions.
11. An operator can reproduce any finding from its evidence bundle without the original runner.
12. Runbooks cover outage, rollback, policy recovery, key rotation, and evaluator revocation.

## Open questions requiring owner decisions

1. What is the authoritative OpenSpec approval mechanism: signed manifest, protected control-plane record, or both?
2. Which assertion classes form the enforced core for the first fleet pilot?
3. What maximum advisory age is acceptable before renewal or automatic escalation?
4. Who may approve repository exceptions, fleet exceptions, and emergency policy rollback?
5. Which architectures must be byte-equivalent at launch?
6. Is offline evaluation a launch requirement or a hardening milestone?
7. What evidence retention periods apply to source findings, release attestations, and 3D captures?
8. Which existing DevGate result fields must remain backward compatible?
9. Which facts in the `gamerepo01` fixture are normative product identity versus historical audit context?
10. Which parts of vision evaluation can meet enforced determinism in the first 3D slice?

## Recommended first thin slice

Use one synthetic repository plus a `gamerepo01`-derived identity fixture. Resolve one approved package, evaluate three deterministic assertions, emit canonical evidence, and run in advisory mode from the pinned container. Then enable Stage 2 ratchet for LobsterWars using its 13 named findings as the fixed baseline. Do not begin with broad AI interpretation, automatic repair, or full-fleet enforcement.

The first three assertion types should be:

1. product identity consistency across package, primary documentation, and artifact metadata;
2. traceability completeness from normative requirement to assertion to evidence;
3. release-claim consistency between package version, built subject digest, and published manifest.

This slice proves the product difference: DevGate is no longer checking only whether code is healthy. It is proving whether the shipped subject is still the thing its approved OpenSpec says it is.

## Review qualification

Fleet reconnaissance (2026-09-17, `TheArchitectit/infra-info`) confirmed `gamerepo01` and LobsterWars-class repositories exist as **real registered fleet repos** (e.g. runner `dell-u2-game`, labels `devgate-game`, repo-scoped to `TheArchitectit/gamerepo01`). However, the specific motivating claims — the gamerepo01 *lineage mismatch narrative* and the LobsterWars *count of 13 advisory violations* — remain supplied context, not facts independently verified from those repositories' contents during this review. A synthetic test may model 13 named findings or an identity drift; it must not be represented as a captured production baseline. Fixtures derived from the real repos require the R9 provenance record (source commit SHA, report digest, capture time, source location) and owner approval before being labeled non-synthetic. See `next-phase-plan.md` and `review.md` R9.
