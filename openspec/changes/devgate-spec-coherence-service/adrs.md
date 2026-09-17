# Architecture decisions proposed for acceptance

All decisions below remain **proposed** until Phase 0 owner review. The word “Decision” preserves the submitted ADR format; it does not record acceptance.

## ADR-001: Build spec coherence as a distinct DevGate service

**Decision:** Add a separate service and result contract rather than overloading existing code-gate semantics.  
**Reason:** Code correctness and conformity to approved product intent are related but different claims.  
**Consequence:** Fleet policy can require either or both, and failures remain explainable.

## ADR-002: Use a pinned, ephemeral container as the reference runtime

**Decision:** The container image digest defines the reference environment.  
**Reason:** Identical runners reduce host drift and create a boundary for filesystem, secrets, resources, and egress.  
**Consequence:** Local and CI adapters must support the same container contract.

## ADR-003: Identify all decision inputs by content digest

**Decision:** Bind subject, OpenSpec, policy, evaluator image, plugins, and evidence by digest.  
**Reason:** Paths, tags, and branches are mutable.  
**Consequence:** Moving references are discovery aids only.

## ADR-004: Keep policy minimums outside repositories

**Decision:** Central policy owns required controls, approved evaluators, and enforcement floors.  
**Reason:** A gated repository cannot be allowed to disable its own gate.  
**Consequence:** Local overlays may strengthen but not weaken policy.

## ADR-005: Separate assertion outcome from enforcement outcome

**Decision:** Record whether a requirement is satisfied independently from whether it currently blocks.  
**Reason:** Advisory adoption must not rewrite violations as success.  
**Consequence:** Debt stays visible through the rollout ladder.

## ADR-006: Make advisory adoption bounded and ratcheted

**Decision:** Require owner, baseline, expiry, and promotion target; block regressions before blocking all inherited debt.  
**Reason:** This avoids both instant fleet breakage and permanent unenforced advisory states.  
**Consequence:** LobsterWars' 13 advisory violations become a migration case, not an accepted steady state.

## ADR-007: Default to no network and least-privilege secrets

**Decision:** Evaluators have no egress or secrets unless a named capability is granted.  
**Reason:** Network and ambient credentials undermine determinism and expand the attack surface.  
**Consequence:** External facts must be captured, digested, and replayable.

## ADR-008: Emit a canonical result plus a noncanonical run envelope

**Decision:** Stable decision data is separated from timestamps, durations, and host telemetry.  
**Reason:** Operational data is useful but must not break replay equivalence.  
**Consequence:** Consumers use canonical data for promotion and envelopes for operations.

## ADR-009: The evaluator never repairs source

**Decision:** The service is read-only with respect to subject and package.  
**Reason:** A gate that silently fixes its inputs destroys auditability and can approve unreviewed intent.  
**Consequence:** Repair loops create a new subject and reevaluate it.

## ADR-010: Reuse one promote-or-halt contract across code and 3D artifacts

**Decision:** Integrations consume the common result contract rather than pipeline-specific pass logic.  
**Reason:** The planned 3D control plane needs the same binding of intent, artifact, evidence, and promotion.  
**Consequence:** Asset and scene assertions can grow without changing the decision protocol.

---

The following ADRs arise from review findings R1–R9 (see `review.md`, design.md v2 amendment log) and are likewise proposed pending Phase 0 acceptance.

## ADR-011: Seal in one acyclic order; attestations and approvals are detached (R1)

**Decision:** Sealing proceeds inputs → evidence → evidence manifest → canonical decision → detached attestation → envelope. No digest, approval, or attestation includes itself or downstream objects.  
**Reason:** The v1 contract embedded `attestation_digest` in the result the attestation signs — a cycle that makes replay and re-signing impossible.  
**Consequence:** Consumers fetch attestations alongside decisions; re-signing never changes decision bytes.

## ADR-012: Time, stage, and captured facts enter through a signed evaluation context (R2)

**Decision:** A versioned, control-plane-issued evaluation-context manifest carries `evaluation_time`, effective stage, baseline/exception identities, capability grants, and captured external facts. Replay and fresh-promotion are distinct semantics; the cache key includes the context.  
**Reason:** Expiry, advisory age, and stage are policy inputs; leaving them ambient or caller-chosen breaks determinism or trust.  
**Consequence:** Repositories cannot pick clocks or stages; historical replay is byte-reproducible but non-authorizing unless re-attested.

## ADR-013: One decision/exit matrix plus a per-assertion ledger (R3)

**Decision:** A single published precedence matrix maps every outcome/error combination to one decision and exit code; completed evaluations emit an `assertion_results` ledger with exactly one entry per planned required assertion; error runs emit structured envelopes with explicit null identities.  
**Reason:** v1 mapped evaluator crashes to ERROR, FAIL, and ADVISORY in different clauses, and violation-only findings could not prove complete accounting.  
**Consequence:** ERROR dominates FAIL within a run; callers resolve exit/result disagreement never in favor of the permissive signal.

## ADR-014: Authority is authenticated, enforcement is external (R4)

**Decision:** Approvals, policy, baselines, exceptions, and stages resolve from control-plane trust roots with anti-rollback; enforcement anchors in required checks/rulesets/promotion controllers outside repository-controlled files.  
**Reason:** Repository-declared `approved` states and self-pinned digests establish identity, not authorization; a deletable workflow is not a gate.  
**Consequence:** Forged approvals, obsolete-policy pinning, and workflow deletion all fail closed.

## ADR-015: Built-in evaluators until a sandbox ADR exists (R5)

**Decision:** Evaluators are bundled, reviewed, deterministic built-ins shipped in the pinned image; repository executable code never runs; a runtime mediator enforces declared-inputs-only access; the launcher — not the container — establishes and verifies isolation. A plugin sandbox (WASI or OS-level per-evaluator isolation) requires its own future ADR.  
**Reason:** An outer hardened container does not isolate co-resident plugins from each other's inputs, environment, or clock.  
**Consequence:** Slice 1 needs no plugin infrastructure; extensibility is deferred deliberately, not accidentally.

## ADR-016: Executable identity profile (R6)

**Decision:** SHA-256 over domain-separated, versioned role tags; restricted RFC 8785 canonical JSON; raw-byte file hashing (normalization applies to representation only); frozen import closure; authenticated normative inventory; input mutation mid-run is ERROR; image index and executed platform digests recorded separately with byte-equivalence promised within an execution profile and semantic equivalence across declared profiles.  
**Reason:** "Normalized" without byte-level rules is not testable, and cross-architecture byte-equivalence conflicts with differing platform digests.  
**Consequence:** Golden vectors are part of the compatibility suite; CRLF changes are content changes.

## ADR-017: Operational assertion schema (R7)

**Decision:** Assertions carry machine-readable requirement refs, owners, typed selectors, schema-validated parameters, and content-derived finding keys. Identity assertions compare against approved package values; release manifests bind an inner payload digest before the outer subject; traceability splits into planning-time structure and post-seal evidence completeness; unpinned model output stays non-canonical advisory evidence.  
**Reason:** v1 assertions could pass on consistent-but-wrong identities, self-reference release digests, and admit non-reproducible model advice into decisions.  
**Consequence:** Slice-1 claims are metadata/identity coherence, honestly labeled — not behavioral proof.

## ADR-018: Signing milestone and retention channels (R8)

**Decision:** Every promotion-authorizing result from Stage 2 onward requires a detached signed attestation; offline local sealing ships in the thin slice with retryable remote upload after seal; exact-input retention for reproduction is an authorized channel distinct from public minimum-disclosure evidence, and retention expiry invalidates cache reuse.  
**Reason:** v1 contradicted itself on when signing becomes mandatory and conflated evidence availability with reproducibility.  
**Consequence:** Stage 2 ratchet demos are attested; evidence outliving retention cannot authorize cached promotion.

## ADR-019: Fingerprinted baselines with provenance rules (R9)

**Decision:** Baselines are sets of finding fingerprints (assertion ID+version, normalized location, content-derived violation key), with defined behavior for version increments, severity escalation, and recurrence after remediation; every pilot fixture records source commit SHA, report digest, capture time, and location, and synthetic fixtures are labeled synthetic.  
**Reason:** Numeric budgets hide regressions at constant counts, and unverified pilot narratives must not masquerade as captured baselines.  
**Consequence:** One-fixed-one-new at count 13 blocks; the gamerepo01 and LobsterWars fixtures start synthetic until provenance capture replaces them.
