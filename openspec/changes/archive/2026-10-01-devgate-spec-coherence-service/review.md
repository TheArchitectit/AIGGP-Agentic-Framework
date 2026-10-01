# Spec coherence package review

**Reviewed:** 2026-09-17  
**Disposition:** Ready for Phase 0 discovery and contract amendment; not ready for implementation contract freeze or enforced rollout.  
**Authority:** Recommendations only. The supplied design and ADRs remain proposed.

## Assessment

The product boundary is strong: deterministic, read-only evaluation against approved intent, separate from ordinary code-health gates. Content-addressed inputs, outcome/enforcement separation, a fingerprinted ratchet, and a shared promotion contract are sound foundations. The package also names useful negative tests rather than relying only on a happy path.

The principal weaknesses are protocol contradictions and unimplemented trust assumptions, not a need for more features. Resolve the blocking findings below before freezing v1. The three-assertion advisory slice is a suitable next build, but it needs evidence sealing and minimum runtime isolation from the start rather than waiting for the end of sequential Phases 1–3.

## Blocking findings

### R1 — Canonical result and attestation form a digest cycle

**Sources:** `design.md`, Canonical result contract and Attestation emitter; `specs/evidence-and-attestation/spec.md`, attestation binding.

The canonical result includes `attestation_digest`, while the attestation must bind the canonical result digest. Computing either requires the completed other object. Signatures, certificates, and signing timestamps can also differ on replay. An approval record's `approved_revision` has a similar self-reference risk if it identifies a digest that includes that same field.

**Proposed amendment:** Define an acyclic sealing order: immutable inputs; evidence objects; evidence manifest; canonical decision; detached attestation; transport envelope. Exclude attestation identifiers and signatures from the canonical decision. Keep package approval detached from the normative bytes it approves. Evidence manifests must not hash themselves or downstream results. Define signed statement bytes, verification policy, and optional-attestation representation explicitly.

**Required tests:** Re-signing leaves decision bytes unchanged; substituted result/evidence fails verification; approval binds exactly the normative digest without hashing its own approval record.

### R2 — Expiry, stage, and captured facts are missing decision inputs

**Sources:** `design.md`, Request contract, Deterministic execution contract, Exception model, and Service availability; `specs/adoption-and-policy/spec.md`.

Advisory age, exception expiry, and cache TTL require a time reference, but the request has none and wall-clock time is forbidden from changing the decision. The requested `mode` does not establish trusted adoption stage. Baselines, exception approvals, capability grants, captured external responses, and revocation state must also be bound inputs; the four-digest cache key does not explicitly cover them.

**Proposed amendment:** Introduce a versioned evaluation-context manifest with a trusted `evaluation_time`, effective stage, baseline/exception identities, capabilities, captured fact digests, and execution profile. These may be transitively bound by policy and context digests, but none may be ambient. The caller cannot choose an older time or weaker stage. Replay uses the original context; a fresh promotion checks time, current authority/revocation, expiry, and the full bound-input key. Signed time/context issuance may occur before offline evaluation. Distinguish replay equivalence from freshness authorization.

**Required tests:** Fixed-context replay is identical; before/at/after expiry has specified outcomes; repository-selected old time is rejected; changed baseline, captured response, grant, or stage invalidates a cached authorization; expired or revoked signatures cannot authorize a new promotion.

### R3 — Error precedence and required-assertion accounting disagree

**Sources:** `design.md`, Result states, Exit codes, and Canonical result contract; `specs/coherence-evaluation/spec.md`, complete required assertion execution; `specs/package-resolution/spec.md`, missing package.

Evaluator crashes can currently mean ERROR, FAIL for an unresolved enforced assertion, or ADVISORY for an unverifiable assertion. Missing packages and malformed exceptions also have multiple possible mappings. `skipped` is in the result summary although the normative terminal outcomes allow only SATISFIED, VIOLATED, and UNRESOLVED. A summary and violation-only findings cannot demonstrate that every required assertion appears exactly once. Invalid input may prevent computing the digests that the success measures require in every result.

**Proposed amendment:** Publish one total decision/exit matrix. Reserve ERROR for invalid input, untrusted policy, evaluator/resource failure, and evidence/signing failure; FAIL for a successfully evaluated blocking policy violation. For a valid planned run, emit an `assertion_results` ledger with one entry per required assertion, independent of zero-or-many findings. Represent a skipped or dependency-blocked required assertion as UNRESOLVED with a stable reason code. Separate complete evaluation results from structured error envelopes; unavailable or unverified identities are explicitly null/absent, never invented. Define deterministic precedence when multiple error classes occur.

**Required tests:** Every stage crossed with every outcome; simultaneous crash and violation; blocked dependencies; missing/malformed output; exit/result disagreement; every exit code including 40; no promotion of ERROR. Inventory may leave unrelated releases unchanged, but it must not issue a positive coherence authorization on an error.

### R4 — Declared authority is not verified authority

**Sources:** `design.md`, OpenSpec package identity, Policy resolver, and Control-plane boundary; `specs/adoption-and-policy/spec.md`, centrally enforced minimums; `specs/integrations/spec.md`, stable CI integration.

`approval.state: approved`, `authority: portfolio-owner`, and expected content digests supplied by a repository do not authenticate approval or fleet policy. A repository could select a genuinely immutable but obsolete/weaker policy, supply its own digest, request advisory mode, or remove the workflow entirely. Digest pinning alone establishes identity, not authorization.

**Proposed amendment:** Define protected trust roots and policy selection outside repository-controlled input. A detached approval binds package digest, authority, repository/subject scope, and validity. Specify anti-rollback and evaluator revocation behavior, the authoritative adoption record, and the overlay merge rules. Enforcement also requires externally managed required-check/ruleset or promotion-controller configuration bound to the trusted producer and exact candidate; a thin workflow is not itself that boundary.

**Required tests:** Forged approvals, trusted-but-obsolete policy, locally reduced stage/severity, disabled assertions, widened selectors/exclusions, unapproved evaluator, removed workflow, result from another commit, and revoked signer/evaluator cannot authorize promotion.

### R5 — A hardened outer container does not isolate plugins from one another

**Sources:** `design.md`, Container boundary, Plugin boundary, and Evaluator runtime; `specs/container-runtime/spec.md`.

Non-root execution, read-only mounts, and dropped capabilities do not prevent a process inside the container from reading other mounted inputs, inherited environment variables, or the clock. Native code can read time through interfaces that simple environment normalization does not intercept. Multiple plugins in one process cannot receive reliable per-plugin filesystem or secret isolation. A digest identifies approved code but does not provide capability enforcement.

**Proposed amendment:** For the initial slice, use bundled, reviewed deterministic built-ins with no repository executable code, no network, and no secrets. Validate the launch profile outside the container rather than trusting self-reported image identity or mount settings. Decide the future plugin sandbox separately (for example, a capability-limited interpreter/WASI runtime or per-evaluator OS isolation with explicit mounts). Specify how each forbidden capability is actually denied; do not claim arbitrary native plugins are deterministic because they run in a container. Keep acquisition and signing outside evaluators. Make `/output` a designated bounded writable volume alongside scratch, or atomically export from scratch after sealing.

**Required tests:** Undeclared input access, sibling-secret access, time/entropy access, unexpected subprocess, forbidden egress, writable input, host socket, and output overflow. Test the approved launcher and supported sandbox, not just a Dockerfile inspection.

### R6 — Digest/canonicalization and platform identity need executable definitions

**Sources:** `design.md`, Subject resolver, OpenSpec resolver, and Deterministic execution contract; `tasks.md`, Phases 1, 2, and 7.

“Normalized” does not specify exact bytes. Imports, Unicode/path collisions, symlink traversal, executable bits, submodules, archive metadata, number formatting, and mutable input races affect identity. Normalizing source line endings can conceal a real artifact change. An OCI image index can be shared across architectures, while its platform image manifests have different digests; putting those differing digests into canonical results conflicts with cross-architecture byte equivalence.

**Proposed amendment:** Recommend SHA-256 with domain-separated/versioned manifest formats and RFC 8785 canonical JSON restricted to supported data types and exact integer ranges. Hash file payloads as raw bytes; normalize manifest representation only under a specified profile. Reject path escapes, unsupported entries, duplicate keys, and normalization collisions. Freeze import closure and require an authenticated normative inventory so a repository cannot hide requirements as informative. Snapshot or verify inputs around evaluation to prevent mutation after hashing. Define image-index identity, executed platform identity, and execution profile explicitly. State whether launch acceptance promises same-profile byte equivalence or cross-profile semantic equivalence; do not promise both without resolving identity fields.

**Required tests:** Golden byte/digest vectors; CRLF/raw-byte mutation; Unicode/path ambiguity; archive traversal; identical and contradictory duplicate IDs; import cycles/digest mismatch; submodule and symlink policy; mutation between manifest and execution; architecture-aware replay comparisons.

### R7 — Assertions are not yet operationally testable or demonstrably semantic

**Sources:** `design.md`, Assertion model; `specs/coherence-evaluation/spec.md`, semantic assertion traceability; `acceptance.md`, Recommended first thin slice.

The example lacks the required owner, normative requirement IDs, extraction rules for README text, and a defined artifact metadata format. Equality between two wrong labels would pass without comparison to approved identity. Traceability is partly a planner invariant and partly an evaluator assertion, creating ordering ambiguity when the checked evidence has not yet been sealed. Release claims can also become self-referential if an embedded manifest claims the digest of a bundle containing that manifest. A reproducible vision rubric does not make an unpinned stochastic model reproducible.

**Proposed amendment:** Add machine-readable requirement IDs, explicit testable/informative status, ownership, typed selectors, evaluator parameters, and stable finding-key rules. Compare all declared identity fields to the approved package value. Define traceability planning checks separately from post-execution evidence-completeness checks. Bind a release manifest to an inner build payload digest, then digest the outer subject that contains both. For the first slice, structured documentation metadata is acceptable, but label it metadata coherence rather than proof of arbitrary executable behavior. Add behavioral probes later as explicit approved evaluators. Keep model-generated advice outside the canonical promotion payload unless every determining input and execution behavior is reproducible.

**Required tests:** Two matching but unapproved identities; missing selector; orphan requirement; renamed/deleted required assertion; assertion with no evidence; valid release manifest for a different build; repaired payload; advisory-model output changes that do not change the deterministic result.

## Additional launch decisions

### R8 — Enforcement milestones and evidence availability are inconsistent

Stage 2 already blocks regressions, while signing is described both as required before enforced promotion and “before Stage 3.” Clarify whether all promotion-authorizing Stage 2 results require signatures; recommendation: yes. Offline normal evaluation is promised in design but listed as an open launch question. Recommend offline local sealing for the thin slice, with remote storage deferred. Separate local sealing failures from retryable remote uploads; policy must say whether confirmed remote durability is a promotion prerequisite.

Minimal-disclosure evidence plus digests alone cannot recreate unavailable source. Define authorized retention/retrieval of exact input bundles separately from public evidence. State cache invalidation on expired retention and how a verifier detects absent evidence. Retention duration and approver identities remain owner decisions.

### R9 — Pilot provenance and debt lifecycle are not established

The submitted `gamerepo01` narrative and LobsterWars count of 13 are motivation, not verified evidence in this checkout review. Do not manufacture game lineage, owners, ages, or finding identities. Record pilot commit SHA, source report digest, capture time, and source locations before calling a fixture derived from verified facts. A synthetic 13-finding model is useful but must be labeled synthetic.

Define fingerprint composition, severity/version changes, approved baseline updates, and what happens when fixed debt recurs. Recommendation: central baseline entries are removed when remediation is accepted; subsequent recurrence blocks. Test replacement of one fixed finding by one new finding while the total remains 13. Numeric-count tests alone cannot prove a ratchet.

## Recommended disposition

Proceed with Phase 0 and close R1–R7 before coding against the protocol. Resolve R8 before any promotion-authorizing pilot; satisfy R9 before presenting pilot findings as captured facts. Keep service scope narrow. Do not change existing gates, pilot repositories, branch protections, or fleet enforcement as part of this document review.

## Persistence changes from the supplied package

- Split the single-file package into its eleven mapped files; retained the full proposed roadmap, ADRs, and acceptance content.
- Added `## ADDED Requirements`, changed requirements to level 3 and scenarios to level 4 to match OpenSpec delta grammar.
- Added eight scenarios to requirements that had none: reproducible findings, minimal disclosure, ephemeral isolation, least-privilege secrets, bounded execution, stable CI integration, fleet visibility, and no implicit trust from upstream. These are direct acceptance restatements, not resolution of the protocol findings above.
- Added status/provenance qualifications and package navigation to distinguish supplied claims from verified facts and proposed decisions from accepted ones.
- Added this review and `next-phase-plan.md`; no substantive contract recommendation has been silently applied to the supplied design.
