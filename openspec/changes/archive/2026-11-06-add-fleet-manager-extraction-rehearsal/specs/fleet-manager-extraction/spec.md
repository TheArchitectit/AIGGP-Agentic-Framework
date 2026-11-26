# Spec: Fleet Manager extraction rehearsal

## ADDED Requirements

### Requirement: The boundary package builds and tests from declared inputs alone
<!-- id: repo-005-01 -->
CI SHALL copy `fleet-manager/` into an isolated workspace containing only that
package and its declared build inputs, and SHALL run the package's test suite
there. The workspace SHALL be asserted to hold no other open-core file, so a
pass cannot come from a module that happened to be nearby. The declared build
inputs SHALL be pinned against the package's declared import surface.

#### Scenario: a hidden repository-relative import

- **WHEN** the extracted copy needs any open-core file outside the declared
  build inputs
- **THEN** phase A fails and names the file the workspace gained or the import
  that could not be satisfied

### Requirement: The open core builds and tests with the boundary absent
<!-- id: repo-005-02 -->
CI SHALL copy the repository without `fleet-manager/` and SHALL prove that the
core test suite still collects and the pattern scan still passes. A collection
that yields no tests SHALL be a failure, not a pass.

#### Scenario: a core module starts depending on the boundary

- **WHEN** any core file imports or names the boundary in a way the boundary
  gate does not already refuse, but which breaks collection without it
- **THEN** phase B fails during collection and names the workspace

#### Scenario: collection finds nothing

- **WHEN** the core suite collects zero tests in the boundary-absent workspace
- **THEN** phase B fails rather than reporting a green rehearsal

### Requirement: Files allowed to name the boundary are declared and pinned
<!-- id: repo-005-03 -->
A file outside the boundary MAY name the boundary only when the manifest
declares it under `invocation_paths`, and that list SHALL be pinned by a test
so widening it is a reviewed change. An invocation site SHALL NOT be inside the
boundary root, and a file not on the list SHALL still fail the dependency
direction check.

#### Scenario: CI runs the boundary's own suite

- **WHEN** the declared workflow invokes the boundary's tests by path
- **THEN** the boundary gate does not object

#### Scenario: a core module names the boundary

- **WHEN** a file that is not a declared invocation site references
  `fleet_manager` or `fleet-manager/`
- **THEN** the boundary gate exits 1 and names the file and line

#### Scenario: the allowance is declared for a file inside the boundary

- **WHEN** `invocation_paths` names a path under the boundary root
- **THEN** the manifest is refused with exit 2
