## ADDED Requirements

### Requirement: stable CI integration

<!-- id: coh-int-01 -->

A CI adapter MUST invoke the same service protocol used locally and in fleet execution. Per-repository workflow files SHOULD contain only pinned invocation and event wiring, not reimplemented gate logic.

#### Scenario: equivalent local and CI invocation

- **GIVEN** local and CI adapters receive the same immutable inputs and declared environment
- **WHEN** they invoke the pinned service
- **THEN** both use the same protocol and produce equivalent canonical results without repository-specific gate logic.

### Requirement: fleet visibility

<!-- id: coh-int-02 -->

Fleet reporting MUST preserve assertion outcome, enforcement state, advisory age, exception expiry, and immutable identities.

#### Scenario: fleet ingests an advisory result

- **GIVEN** an evaluation records an underlying violation with advisory enforcement
- **WHEN** fleet reporting ingests the result and its run metadata
- **THEN** it preserves the violation, enforcement state, advisory age, exception expiry, and immutable identities.

### Requirement: promote-or-halt contract

<!-- id: coh-int-03 -->

A pipeline consumer MUST promote only PASS results unless its centrally approved policy explicitly accepts ADVISORY for the current stage.

#### Scenario: 3D asset candidate passes

- **GIVEN** a generated world bundle has immutable asset, scene, build, capture, and evaluation manifests
- **WHEN** all required OpenSpec assertions pass
- **THEN** the service emits PASS and a promotion system may advance the exact subject digest.

#### Scenario: repair changes the candidate

- **GIVEN** a bounded repair produces a new asset or scene digest
- **WHEN** promotion is reconsidered
- **THEN** the previous result is invalid for the new subject and the full required gate runs again.

#### Scenario: vision advice is nondeterministic

- **GIVEN** a vision model supplies a subjective observation
- **WHEN** deterministic promotion policy is applied
- **THEN** the observation is labeled advisory unless a versioned deterministic rubric and captured inputs make it reproducible; it cannot silently become an enforced pass.

### Requirement: no implicit trust from upstream

<!-- id: coh-int-04 -->

An upstream build success, test pass, or signed artifact MUST NOT substitute for spec-coherence evaluation. Such records may be inputs to explicit assertions.

#### Scenario: upstream artifact is signed but unevaluated

- **GIVEN** an upstream artifact has a valid signature or successful build record
- **WHEN** it has not undergone the required spec-coherence evaluation
- **THEN** the upstream record does not substitute for a coherence decision.

### Requirement: adapters never weaken the contract

<!-- id: coh-int-05 -->

No adapter (CI, local, fleet, pipeline) may reinterpret, re-rank, or downgrade a canonical decision. Adapters transport decisions; they do not compute them. An adapter that cannot obtain a parseable canonical result MUST surface ERROR semantics, never a default-allow.

#### Scenario: adapter timeout

- **GIVEN** a CI adapter times out waiting for the service result
- **WHEN** it reports to its platform
- **THEN** it reports a failed/error check, never a neutral or passing one.

### Requirement: gate runs or reports explicit SKIPPED

<!-- id: coh-int-06 -->

Consistent with the fleet CI-template contract (`ci-run-01`), a named coherence gate MUST either actually execute or report an explicit SKIPPED status with a reason. It MUST NOT silently pass, and a SKIPPED on a repository whose policy requires coherence MUST be treated by the hub as a non-passing condition, never as green.

#### Scenario: coherence gate cannot run

- **GIVEN** a repository whose coherence gate cannot resolve a pinned runtime or package
- **WHEN** the CI workflow reports its conclusion
- **THEN** it reports SKIPPED with a reason (or a failed check), and the hub-side check class records a non-passing state rather than absence-as-pass.

### Requirement: per-repository fleet independence

<!-- id: coh-int-07 -->

Fleet integration MUST respect that runners are repo-scoped and the hub polls each registered repository independently. A coherence check class MUST be evaluated per registered repo against that repo's watched branches, and MUST NOT assume one runner can evaluate another repository's subject. Alert deduplication follows the existing `(repo, check-class, runner)` key.

#### Scenario: hub polls a registered repo

- **GIVEN** the hub iterates its registered repositories (each with its own repo-scoped runner)
- **WHEN** it evaluates the coherence check class for a repo on its watched branches
- **THEN** it consumes that repo's own coherence workflow conclusion and raises a deduped alert under that repo, never borrowing another repo's result.

#### Scenario: watched-branch scope

- **GIVEN** a host whose watched branches are configured (e.g. `main`)
- **WHEN** the coherence check class runs
- **THEN** it evaluates only the configured watched branches and records an explicit no-op (not a pass) where none are configured.
