# Spec Delta: container-runtime (fix-coherence-container-contract)

## ADDED Requirements

### Requirement: Evaluator image self-containment
<!-- id: coh-rt-08 -->
The pinned evaluation image SHALL contain every runtime contract the service
loads at request time. The service SHALL resolve contract schemas (and any
other frozen data it reads) relative to its own package location, never
relative to repository or change-package layout. A container built from the
recorded Containerfile SHALL be able to load all frozen schemas and complete a
valid request without referencing any path outside the image.

#### Scenario: schema load inside the container
- **WHEN** the pinned image runs and the service loads a frozen contract schema
- **THEN** the schema resolves from inside the image and no file outside the
  image is read

#### Scenario: archiving a change package does not affect runtime
- **WHEN** an OpenSpec change package that once carried frozen schemas is
  archived or renamed
- **THEN** the service's schema resolution is unaffected because runtime
  schemas live in the service package, not the change package

### Requirement: Container smoke evidence includes a success path
<!-- id: coh-rt-09 -->
Real-container smoke evidence for the evaluator image SHALL include at least
one valid request that completes with a non-ERROR decision, in addition to any
honest-rejection cases. An exit code that a broken service can also produce
(for example, exit 30 from a failure to load contracts) SHALL NOT be the only
assertion, and rejection cases SHALL assert a reason that names the invalid
input rather than an I/O error.

#### Scenario: broken image cannot pass smoke evidence
- **WHEN** the image cannot load its frozen schemas (contracts missing from
  the image)
- **THEN** the smoke evidence fails, because the valid-request case cannot
  produce a non-ERROR decision

#### Scenario: honest rejection is distinguishable
- **WHEN** a malformed request is evaluated in-container
- **THEN** the emitted envelope's reason identifies the invalid field, and the
  test asserts on that reason, not only on the exit code
