# Surface Reach

## ADDED Requirements

### Requirement: A change must reach every declared surface
<!-- id: srch-01 -->
Every declared surface of a single artifact MUST contain identical content, or the gate
MUST fail naming the surfaces that did not receive the change. A fix verified on one
surface MUST NOT be recorded as complete while another declared surface still holds the
old content.

#### Scenario: fix applied to one of two surfaces
- **WHEN** two declared copies of a shared component differ in content
- **THEN** the gate fails naming the odd-one-out surface rather than reporting the group as done

#### Scenario: all surfaces agree
- **WHEN** every declared surface hashes identically
- **THEN** the gate passes and reports the surface count

### Requirement: A vanished surface is a failure, not a skip
<!-- id: srch-02 -->
A declared surface that no longer exists MUST fail the gate. A missing surface is the
loudest form of "the change did not reach it", and silently skipping it converts a
regression into a passing check.

#### Scenario: surface deleted
- **WHEN** one declared path in a group does not exist
- **THEN** the gate fails naming the missing path

### Requirement: Comparison mode is declared per group
<!-- id: srch-03 -->
Each group MUST declare how surfaces are compared: `hash` for content identity, or
`exists` for generated artifacts where identical bytes are not expected. An undeclared
mode MUST default to `hash`, because content divergence is the failure this gate exists to
catch.

#### Scenario: generated artifact group
- **WHEN** a group declares `"compare": "exists"` for build outputs
- **THEN** presence is checked and byte identity is not required

### Requirement: A group with fewer than two surfaces is a configuration error
<!-- id: srch-04 -->
A declared group with fewer than two paths MUST fail, and an empty manifest MUST exit with
the nothing-scanned code. A surface comparison over one path verifies nothing.

#### Scenario: single-path group
- **WHEN** a group declares one path
- **THEN** the gate fails stating a comparison needs at least two surfaces

#### Scenario: empty manifest
- **WHEN** the manifest declares no groups
- **THEN** the gate refuses with a vacuous-pass message
