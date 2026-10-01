## ADDED Requirements

### Requirement: assertion schema is operational

<!-- id: coh-assert-01 -->

Every assertion MUST declare, in machine-readable form: a globally stable ID and version; one or more normative requirement references; an owner; testable requirement language; typed subject selectors; an approved evaluator ID and digest; typed parameters validated against the evaluator's published schema; severity; evidence expectations; and a deterministic dependency set. An assertion missing any required property is a structural package error.

#### Scenario: assertion missing owner or requirement ref

- **GIVEN** an assertion omits its owner or normative requirement reference
- **WHEN** the package is validated
- **THEN** the package is rejected as structurally invalid, naming the assertion and missing property.

#### Scenario: parameter schema violation

- **GIVEN** assertion parameters that do not validate against the evaluator's published parameter schema
- **WHEN** the planner builds the graph
- **THEN** planning fails before execution with a stable reason code.

### Requirement: identity assertions compare against approved values

<!-- id: coh-assert-02 -->

A product-identity assertion MUST compare declared identity fields against the approved value recorded in the package, not merely assert that multiple declared fields agree with each other. Two matching but unapproved identities MUST NOT satisfy the assertion.

#### Scenario: consistent but unapproved identity

- **GIVEN** README and artifact metadata both declare product name "X" while the approved package records "Y"
- **WHEN** the identity assertion evaluates
- **THEN** the assertion is VIOLATED with both observed and expected values recorded.

#### Scenario: selector resolves to nothing

- **GIVEN** a declared artifact-metadata selector that matches no field in the subject
- **WHEN** the assertion evaluates
- **THEN** the outcome is UNRESOLVED with reason `selector-empty`, never SATISFIED.

### Requirement: release-claim binding order

<!-- id: coh-assert-03 -->

A release-claim assertion MUST bind the release manifest to an inner build-payload digest first, then treat the outer subject (which may contain the manifest) as a separate digest. A manifest MUST NOT be allowed to claim the digest of a bundle that contains the manifest itself.

#### Scenario: self-referential release manifest

- **GIVEN** a release manifest whose claimed digest is the digest of the bundle containing that manifest
- **WHEN** the release-claim assertion evaluates
- **THEN** the circular claim is rejected as invalid input for that assertion, recorded UNRESOLVED or VIOLATED per the matrix, never SATISFIED.

#### Scenario: manifest for a different build

- **GIVEN** a valid release manifest whose bound inner payload digest does not match the subject's build payload
- **WHEN** the assertion evaluates
- **THEN** the assertion is VIOLATED and the mismatched digests are recorded.

### Requirement: traceability checks are separated by phase

<!-- id: coh-assert-04 -->

Traceability MUST be enforced at two distinct points with distinct semantics: a planning-time structural check (every assertion references a real normative requirement; every testable requirement has an assertion) that runs before evaluators, and a post-execution evidence-completeness check (every VIOLATED enforced finding has sealed evidence) that runs after sealing. Planning-time traceability MUST NOT depend on evidence that does not yet exist.

#### Scenario: planning check runs first

- **GIVEN** a package with an orphan testable requirement
- **WHEN** the planner runs before any evaluator
- **THEN** traceability violation is detected at planning and enforced policy blocks without requiring evaluator execution.

### Requirement: model-generated advice is non-canonical

<!-- id: coh-assert-05 -->

Output from a stochastic or unpinned model (including vision models) MUST NOT enter the canonical decision payload as an enforced finding unless every determining input and the model execution itself are versioned, pinned, captured, and reproducible under the determinism contract. Otherwise such output is labeled advisory evidence and cannot by itself produce or block a PASS.

#### Scenario: advisory vision observation

- **GIVEN** a vision model observation about a 3D capture supplied without a pinned reproducible rubric
- **WHEN** the decision is computed
- **THEN** the observation is recorded as advisory evidence only; it never changes an enforced outcome and never silently becomes an enforced pass.

#### Scenario: reproducible rubric met

- **GIVEN** a model-based assertion whose rubric, model digest, inputs, and seed are all pinned and captured
- **WHEN** it is replayed
- **THEN** it produces identical output and MAY participate as a deterministic assertion under the normal contract.

### Requirement: finding key stability

<!-- id: coh-assert-06 -->

Each finding MUST carry a stable finding key derived from deterministic content (assertion ID, normalized subject location, violation class), used for baseline fingerprinting and deduplication. Keys MUST NOT derive from timestamps, memory addresses, or nondeterministic ordering.

#### Scenario: same violation across runs

- **GIVEN** the same assertion violated at the same subject location in two runs
- **WHEN** finding keys are computed
- **THEN** the keys are identical, enabling stable baseline fingerprinting.
