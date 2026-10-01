# DevGate Spec Coherence Service

**Status:** Proposed for review  
**Date:** 2026-09-17  
**Working change ID:** `devgate-spec-coherence-service`  
**Scope:** A containerized, deterministic service that verifies shipped code and artifacts still conform to the OpenSpec package that authorized them.

## Summary

DevGate currently gates code quality and delivery mechanics. This change adds a separate gate for product meaning: whether the code and artifacts being shipped still match the approved OpenSpec package that produced them.

The service runs as a pinned container with identical, ephemeral execution for every repository. It resolves an immutable OpenSpec package, evaluates deterministic assertions against a declared subject, emits machine-readable evidence, and returns an advisory or enforced decision according to repository policy. The service is shared infrastructure rather than copied workflow logic.

## Why

### Problem

A repository can pass lint, tests, build, and security checks while no longer being the product its governing documents describe. Conventional CI proves that code behaves consistently with its tests. It does not prove that the repository's implementation, documentation, assets, interfaces, and release claims remain coherent with an approved design.

The motivating failure is the `gamerepo01` lineage mismatch. Its repository materials described different games and lineages. The code could remain buildable while the README, design story, and current implementation disagreed. That is a spec-coherence failure. It creates false release claims, bad migration decisions, and audits that repeat stale narratives.

A second failure mode is policy that never becomes real. LobsterWars carried 13 advisory violations without enforcement. Advisory findings are useful during adoption, but an advisory state without an owner, deadline, and promotion rule becomes permanent bypass. This package makes the adoption ladder explicit and measurable.

## What Changes

Add the separate spec-coherence service described in this proposed package: immutable package and subject resolution, deterministic evaluators, evidence and attestations, centrally controlled adoption policy, an isolated container runtime, and thin CI/fleet/pipeline adapters.

### Desired outcomes

1. Every evaluated release is tied to an immutable OpenSpec package identity.
2. The same inputs, evaluator image, policy bundle, and declared environment produce the same decision and evidence.
3. A repository cannot silently skip or replace required coherence assertions.
4. Advisory adoption has an owner, budget, deadline, and promotion criteria.
5. Enforced violations prevent promotion through a stable exit and result contract.
6. Evaluation happens in an ephemeral, pinned container with bounded filesystem, secrets, and network access.
7. Results are useful to people and composable by machines.
8. The 3D asset pipeline can use the same decision contract for promote-or-halt.

## Product boundary

The service answers one question:

> Does this exact subject conform to this exact approved OpenSpec package under this exact policy and evaluator version?

It does not replace:

- unit, integration, security, licensing, or performance tests;
- OpenSpec authoring or human design review;
- artifact generation, scene editing, or repair planning;
- repository history analysis when lineage has not been declared;
- subjective vision judgment unless that judgment is converted into a versioned, deterministic assertion or supplied as separately labeled advisory evidence;
- deployment orchestration.

## Users and calling systems

- repository maintainers adopting coherence checks;
- DevGate fleet operators managing common policy;
- release automation requiring a promote-or-halt decision;
- audit tooling consuming evidence and attestations;
- the planned 3D design pipeline, which needs a stable promotion gate after build, capture, and evaluation.

## Success measures

- 100% of service results include subject digest, package digest, evaluator digest, policy digest, and evidence manifest digest.
- Replaying a conformance fixture 100 times on supported runners produces byte-equivalent canonical result JSON.
- No enforced repository can merge or promote when required assertions are absent, skipped, unresolved, or executed by an unapproved evaluator.
- Every advisory exception has an owner, reason, expiry, and enforcement target.
- No repository remains indefinitely in advisory mode without an explicit renewed exception.
- The first 3D vertical slice can consume the result contract without pipeline-specific branching.

## Risks

- False confidence if assertions prove document presence rather than implementation meaning.
- Nondeterminism from clocks, network calls, locale, file ordering, generated IDs, or unpinned tools.
- Excessive noise causing maintainers to bypass the service.
- Central service failure blocking the fleet.
- Spec packages that are vague, contradictory, or not testable.
- Secrets or source escaping through plugins or network access.
- A weak advisory policy repeating the LobsterWars anti-pattern.

## Package map

- `proposal.md`: rationale, boundary, outcomes, and non-goals.
- `design.md`: architecture, trust boundaries, contracts, and rollout — **v2, amended per review R1–R9** (amendment log at end).
- `specs/package-resolution/spec.md`: package discovery, identity, imports, normative inventory.
- `specs/coherence-evaluation/spec.md`: deterministic evaluation, ledger, traceability.
- `specs/canonical-identity/spec.md`: digest/canonicalization profile, subject manifests, image identity.
- `specs/decision-contract/spec.md`: decision/exit matrix, error envelopes, canonical separation.
- `specs/evaluation-context/spec.md`: context manifest, trusted issuance, replay vs fresh promotion, cache keys.
- `specs/evidence-and-attestation/spec.md`: sealing order, evidence, detached attestation, retention.
- `specs/adoption-and-policy/spec.md`: adoption ladder, ratchet fingerprints, exceptions, external enforcement.
- `specs/assertions-and-evaluators/spec.md`: operational assertion schema, built-in evaluators, model advice.
- `specs/container-runtime/spec.md`: launcher-validated isolation, egress, secrets, bounds.
- `specs/subjects-3d/spec.md`: composite 3D subjects, repair invalidation, captures.
- `specs/integrations/spec.md`: CI, fleet, and pipeline integration.
- `tasks.md`: full-program sprint plan S0–S8 with gates.
- `adrs.md`: ADR-001…010 as submitted plus ADR-011…019 from the review; all proposed pending acceptance.
- `acceptance.md`: fixtures, acceptance tests, and open owner decisions.
- `stage3-readiness.md`: the 12 release acceptance criteria dispositioned with cited evidence; the input package for the Stage 3 readiness review that gates enforced rollout.
- `review.md`: review findings R1–R9; the amendments they produced are embodied in design v2 and the specs above.
- `next-phase-plan.md`: repository-grounded immediate handoff (superseded in detail by `tasks.md` S0–S8).

Normative terms MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are used in the RFC 2119 sense.

## Persistence and review status

The supplied package is preserved as a proposal, not an approved product package or evidence of pilot-repository facts. OpenSpec requirement/scenario heading levels are normalized for delta validation. Scenario additions required by validation are documented in `review.md`. No ADR, policy authority, or pilot baseline is accepted by saving these files. Contract amendments in the review require explicit acceptance before implementation.
