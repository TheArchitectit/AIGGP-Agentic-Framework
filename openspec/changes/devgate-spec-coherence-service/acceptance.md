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

### Decided (2026-09-26)

**Q1, Q2, Q3, Q4, Q5, Q9 were answered by the owner** — all six proposed
defaults from `s1-freeze-record.md` §7 accepted as written: (1) detached
control-plane approval record binding package digest + authority + repo
scope + validity window; (2) enforced core = product-identity consistency,
traceability completeness, release-claim consistency; (3) max advisory
age **30 days**, renewable once with owner + written reason + new expiry +
control-plane approval; (4) control-plane authority approves fleet
exceptions and emergency rollback; repository exceptions additionally
require the repo maintainer's countersign; (5) amd64-only byte-equivalence
at launch, arm64 semantic-equivalence until provisioned; (9) gamerepo01
fixture starts synthetic — normative identity is the package's declared
identity, historical lineage is informative. Q6–Q8 and Q10 remain open
and do not gate Stage 3 (see `stage3-readiness.md`).

**Evaluator revocation — decided 2026-09-26 (separate question from the
six):** scope to the **pinned-image lifecycle**. A bad evaluator image is
retired by re-pinning (`scripts/re-pin-evaluator-identity.sh`); old
attestations remain valid for what they proved at their evaluation time;
no new control-plane revocation record is built. `verify()` checks the
signer, not the evaluator's present-time standing — that separation of
attestation-time validity from pin-time standing is the accepted
semantics.

**Q6 and Q7 — decided 2026-09-28 (owner, via structured question):**

- **Q6 (offline evaluation): hardening milestone, not a launch
  requirement.** Enforcement stages (2+) require offline verification;
  stages 0–1 may fetch at evaluation time. This matches the design's
  existing posture: promotion-authorizing results already require the
  pinned image and signer set available locally.
- **Q7 (evidence retention): adopt the shipped retention-class default
  as-is** — short (7d, PASS runs), standard (30d, ADVISORY), extended
  (1y, FAIL/ERROR + attested bundles). Zero new code; the fallback
  already enforces this, so the decision ratifies shipped behavior.

With these two, the open-question set reduces to Q8 (backward-compatible
result fields) and Q10 (vision determinism, S7) — neither gates Stage 3.

## Recommended first thin slice

Use one synthetic repository plus a `gamerepo01`-derived identity fixture. Resolve one approved package, evaluate three deterministic assertions, emit canonical evidence, and run in advisory mode from the pinned container. Then enable Stage 2 ratchet for LobsterWars using its 13 named findings as the fixed baseline. Do not begin with broad AI interpretation, automatic repair, or full-fleet enforcement.

The first three assertion types should be:

1. product identity consistency across package, primary documentation, and artifact metadata;
2. traceability completeness from normative requirement to assertion to evidence;
3. release-claim consistency between package version, built subject digest, and published manifest.

This slice proves the product difference: DevGate is no longer checking only whether code is healthy. It is proving whether the shipped subject is still the thing its approved OpenSpec says it is.

## Review qualification

Fleet reconnaissance (2026-09-17, `TheArchitectit/infra-info`) confirmed `gamerepo01` is a **real registered fleet repo**: runner `dell-u2-game`, labels `devgate-game`, repo-scoped to `TheArchitectit/gamerepo01` (re-verified against infra-info at `3e156ba` on 2026-09-24). **Re-checked 2026-09-25 against the live GitHub API, after the two-tier rebalance corrected the host but not the registration:** `gamerepo01` still has a real runner, now `ucs03-game` (labels `devgate-game,devgate`) — `dell-u2-game` and `u85-game` are offline (the former archived, the latter paused for a hardware swap), so any citation naming `dell-u2-game` as *the* runner is stale.

The LobsterWars-class half of that sentence did **not** survive the 2026-09-24 re-check and is corrected here: infra-info held no registration, runner entry, or label for the games repo (`gamerepo02`, package `lobsterbot-glitch-wars`) — its workflows targeted a `devgate-gamerepo02` label with no recorded runner behind it. **That gap has since closed** (measured 2026-09-25): `ucs03-gamerepo02` is registered, **online**, and carries `devgate-gamerepo02,devgate`, with `dell-u2-gamerepo02` retained offline. So a runner now exists behind that label; what does not follow is any claim about the repo's *contents*.

Regardless of runner existence, the specific motivating claims — the gamerepo01 *lineage mismatch narrative* and the LobsterWars *count of 13 advisory violations* — remain supplied context, not facts independently verified from those repositories' contents during this review. A synthetic test may model 13 named findings or an identity drift; it must not be represented as a captured production baseline. Fixtures derived from the real repos require the R9 provenance record (source commit SHA, report digest, capture time, source location) and owner approval before being labeled non-synthetic. See `next-phase-plan.md` and `review.md` R9.

**Update 2026-09-28 — the capture has run** (`r9-provenance-capture.md`, owner approval granted for read-only inspection). It resolves the two claims asymmetrically, and the asymmetry is itself the finding:

- **LobsterWars (13 violations): CAPTURED.** All four ADR-019 fields are recorded (SHA, run, digest, capture time), and the count of 13 was independently reconstructed from the gate's own run log rather than carried over from the narrative — 12 × `PREVENT-011` + 1 × `PREVENT-029`, with the 16 `PREVENT-012` advisories excluded as non-blocking. This baseline may now be labeled a captured production baseline.
- **gamerepo01 (lineage mismatch): NOT CAPTURED, and cannot be in this form.** The repository carries no `.guardrails/` directory — all four identity probes (`scope.json`, `product.json`, `identity.json`, the directory itself) returned 404 — so it declares no product identity for a lineage to mismatch. The narrative's premise does not hold against the repository's actual contents. The fixture therefore stays synthetic, now by measurement rather than by default, and no report digest is recorded because no gate report ever made the lineage claim.

The rule above is unchanged and still binding: nothing here relabels a fixture on the strength of a narrative. What changed is that one claim now has provenance and the other has a measured reason to be excluded.
