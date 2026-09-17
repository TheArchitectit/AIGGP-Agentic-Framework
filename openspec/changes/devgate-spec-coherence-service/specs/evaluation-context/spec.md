## ADDED Requirements

### Requirement: versioned evaluation context

<!-- id: coh-ctx-01 -->

Every evaluation MUST receive a versioned evaluation-context manifest as a bound, digested input. It MUST carry: a trusted `evaluation_time`, the effective adoption stage, baseline and exception set identities, capability grants, captured external-fact digests, the execution profile, and the supported-runner declaration. None of these values MAY be taken from ambient environment, host clock, or unauthenticated request fields.

#### Scenario: context is a decision input

- **GIVEN** two runs with identical subject, package, policy, and evaluator but different contexts (different stage or expired exception set)
- **WHEN** decisions are computed
- **THEN** the decisions may differ, and each result records its context digest.

#### Scenario: caller cannot pick the clock

- **GIVEN** a request attempts to supply `evaluation_time` inline or via environment
- **WHEN** the invocation adapter validates
- **THEN** the inline value is rejected as an unknown required field or ignored in favor of the signed context, and a repository-supplied context without trusted issuance fails policy resolution (exit 31).

### Requirement: trusted context issuance

<!-- id: coh-ctx-02 -->

The evaluation context MUST be issued or countersigned by the control plane, or derived deterministically from control-plane-published state (stage registry, baselines, exceptions, signer set) at a recorded issuance time. Stage assignment MUST come from the authoritative adoption record, never from the repository's requested `mode`; a requested mode weaker than the recorded stage MUST be rejected.

#### Scenario: repository requests weaker stage

- **GIVEN** the authoritative adoption record places a repository at Stage 2
- **WHEN** its CI requests `mode: advisory` (Stage 1 semantics)
- **THEN** policy resolution fails or the effective stage remains 2, and the attempt is recorded.

#### Scenario: stale context reuse

- **GIVEN** a context issued for an earlier baseline or exception set
- **WHEN** a fresh promotion-time evaluation runs
- **THEN** the stale context is rejected unless replay semantics are explicitly declared (see replay requirement).

### Requirement: replay versus fresh promotion

<!-- id: coh-ctx-03 -->

The service MUST distinguish two evaluation semantics. **Replay** re-executes with the original context to reproduce a historical decision byte-for-byte; replayed results are labeled non-promotion-authorizing unless re-attested under current authority. **Fresh promotion** uses current issued context, current signer set, current revocation state, and current expiry evaluation against `evaluation_time`; only fresh results authorize promotion.

#### Scenario: replay does not authorize

- **GIVEN** a byte-identical replay of a month-old PASS
- **WHEN** a promotion consumer checks freshness
- **THEN** the replay result alone does not authorize promotion; a fresh evaluation (or a policy-valid cached fresh result) is required.

#### Scenario: expiry evaluated at decision time

- **GIVEN** an exception valid at original evaluation time but expired at fresh evaluation time
- **WHEN** a fresh promotion evaluation runs
- **THEN** the exception no longer applies and the underlying violation enforces according to the current stage.

### Requirement: bound external facts

<!-- id: coh-ctx-04 -->

Any external fact an assertion depends on (registry record, upstream attestation, published manifest) MUST enter evaluation as a captured, digested fact in the context, captured under a policy grant. Live fetching inside evaluators is prohibited by the container-runtime spec; captured facts make replays deterministic and fresh runs re-capturable.

#### Scenario: captured fact changes

- **GIVEN** a registry record re-captured for a fresh run differs from the capture bound in the original context
- **WHEN** the fresh evaluation runs
- **THEN** the new capture is used, its digest recorded, and any assertion outcome that depended on the old value is recomputed rather than inherited.

### Requirement: cache key completeness

<!-- id: coh-ctx-05 -->

Signed cached results MUST be reused only when every bound identity matches exactly: subject, package, policy, evaluation-context, evaluator image, plugin digests, and captured-fact digests — and only within policy TTL and while retention and signer validity hold. The four-digest subset is not a sufficient cache key.

#### Scenario: partial key match

- **GIVEN** a cache entry matching subject, package, policy, and evaluator digests but bound to an older context or captured-fact set
- **WHEN** cache lookup runs
- **THEN** the entry is a miss and full evaluation runs.
