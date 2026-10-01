## ADDED Requirements

### Requirement: explicit package resolution

<!-- id: coh-pkg-01 -->

The service MUST resolve exactly one OpenSpec package for an evaluation.

#### Scenario: explicit immutable package

- **GIVEN** the request supplies a package root and expected digest
- **WHEN** the content matches that digest
- **THEN** the service uses the package and records its canonical digest.

#### Scenario: missing package

- **GIVEN** policy requires spec coherence
- **WHEN** no package can be resolved
- **THEN** the service returns invalid input or FAIL according to adoption policy, never PASS.

#### Scenario: moving reference

- **GIVEN** a branch or tag locates the package
- **WHEN** resolution completes
- **THEN** the service records and evaluates the resolved content digest, not the moving name.

### Requirement: package structural validity

<!-- id: coh-pkg-02 -->

The package MUST have a supported schema, unique assertion IDs, resolvable normative references, an acyclic dependency graph, and declared approval state.

#### Scenario: contradictory duplicate ID

- **GIVEN** two normative files define the same assertion ID differently
- **WHEN** the package is validated
- **THEN** evaluation stops with invalid package.

#### Scenario: identical duplicate ID

- **GIVEN** two normative files define the same assertion ID with byte-identical content
- **WHEN** the package is validated
- **THEN** the duplicate is reported as a structural violation with a stable reason code, not silently merged.

### Requirement: normative boundary

<!-- id: coh-pkg-03 -->

The package MUST distinguish normative requirements from informative commentary.

#### Scenario: narrative note changes

- **GIVEN** only informative text changes
- **WHEN** identity is recomputed
- **THEN** the normative package digest remains stable and the full archive digest may change separately.

### Requirement: frozen import closure

<!-- id: coh-pkg-04 -->

Package imports MUST resolve to digested content inside the frozen closure before evaluation; an import MUST NOT be resolved lazily from a mutable reference at evaluation time.

#### Scenario: import digest mismatch

- **GIVEN** a declared import's resolved content does not match its recorded digest
- **WHEN** the package is validated
- **THEN** evaluation stops with invalid package and records both digests.

#### Scenario: import cycle

- **GIVEN** package imports form a cycle
- **WHEN** the closure is resolved
- **THEN** evaluation stops with invalid package and names the cycle.

### Requirement: authenticated normative inventory

<!-- id: coh-pkg-05 -->

The set of normative files MUST be fixed by an authenticated inventory in the package manifest; a repository MUST NOT be able to reclassify a normative file as informative, or omit one from the inventory, without changing the package digest and invalidating approval.

#### Scenario: requirement hidden as informative

- **GIVEN** a file containing normative requirements is declared informative
- **WHEN** package validation runs the normative/informative classifier rules
- **THEN** the package is rejected as structurally invalid with the offending file named.
