## ADDED Requirements

### Requirement: project root resolves by layout, never by ancestor search

A scanner SHALL resolve the project root from its own file location by layout: if
its own directory is named `.devgate`, the project root is that directory's
parent (submodule layout); otherwise the scanner's own directory IS the project
root (standalone layout). A scanner SHALL NOT choose a root by searching
ancestors for a marker file such as `package.json` or `.git`.

<!-- id: root-anchor-01 -->

#### Scenario: standalone checkout under a marker-bearing parent

- **GIVEN** a standalone checkout whose parent directory carries its own package.json
- **WHEN** a scanner resolves its project root
- **THEN** the root is the checkout, and files in the parent are not evaluated

#### Scenario: submodule checkout

- **GIVEN** DevGate installed at `<project>/.devgate/`
- **WHEN** a scanner resolves its project root
- **THEN** the root is `<project>`, so the consumer's own files are evaluated

### Requirement: a test runner fails closed on zero discovery

A test runner SHALL treat discovery of zero test files as a failure with a
stated reason, and SHALL NOT exit successfully. It MAY offer an explicit opt-out
that prints a distinguishable skip message, so a project with genuinely no tests
records a skip rather than a pass. A runner that evaluates nothing is
indistinguishable from one that evaluated everything and found it clean.

<!-- id: root-anchor-02 -->

#### Scenario: no tests found

- **GIVEN** a directory laid out as a project with no test files in any scanned location
- **WHEN** the runner executes
- **THEN** it exits nonzero and reports that no test files were discovered

#### Scenario: explicit skip requested

- **GIVEN** the same directory with the opt-out enabled
- **WHEN** the runner executes
- **THEN** it exits zero and states that it skipped, not that it passed

### Requirement: every scanner shares one root contract

The scanners that resolve a project root SHALL import a single shared
implementation of the layout contract rather than each carrying its own copy,
so that a future scanner cannot reintroduce an ancestor search by copying two
lines from an older one.

<!-- id: root-anchor-03 -->

#### Scenario: a second copy appears

- **GIVEN** a new scanner that reimplements root resolution by walking ancestors
- **WHEN** the anchoring fixture runs
- **THEN** the fixture's escape cases fail, because they exercise the shared
  contract rather than the new scanner's private copy
