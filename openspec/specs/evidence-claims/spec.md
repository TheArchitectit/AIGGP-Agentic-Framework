# evidence-claims Specification

## Purpose
What a deferred item, mock, stub or exemption is allowed to claim. A marker must name owner, reason and expiry; a mock points at the real thing it stands in for; a stub references a tracked issue; exemptions are declared, never inferred from prose.

## Requirements

### Requirement: A deferred marker must name owner, reason, and expiry
<!-- id: evc-01 -->
Any `DEFERRED` marker in tracked source MUST carry `owner`, `reason`, and a `review` date.
A marker missing any field MUST fail. A `review` date in the past MUST fail, because an
expired deferral is an unmade decision wearing the costume of one.

#### Scenario: ownerless deferral
- **WHEN** a marker reads `DEFERRED(reason="blocked", review=2027-01-01)` with no owner
- **THEN** the gate fails naming the missing field, because nobody is accountable for the wait

#### Scenario: expired deferral
- **WHEN** a marker's `review` date is in the past
- **THEN** the gate fails stating the deferral expired and must be re-decided or removed

### Requirement: A mock must point at the real thing it stands in for
<!-- id: evc-02 -->
Any `MOCK` marker MUST carry a `src` reference to the real source it substitutes and a
`why` explanation. A mock with no pointer is an assumption, not a test fixture.

#### Scenario: mock with source pointer
- **WHEN** a marker reads `MOCK(src="docs/fixtures/orders.json", why="sandbox unavailable")`
- **THEN** the gate passes and a reviewer can follow the reference

#### Scenario: bare mock
- **WHEN** mock data appears with no `src` pointer
- **THEN** the gate fails, because nothing distinguishes the stand-in from the real contract

### Requirement: A stub must reference a tracked issue
<!-- id: evc-03 -->
Any `STUB` marker MUST carry an `issue` identifier and a `why`. A stub that names no
tracked work is indistinguishable from unfinished code that nobody intends to finish.

#### Scenario: stub with issue
- **WHEN** a marker reads `STUB(issue="AIGGP-412", why="interface frozen, impl next sprint")`
- **THEN** the gate passes

#### Scenario: stub with no issue
- **WHEN** a stub marker carries no `issue`
- **THEN** the gate fails naming the missing field

### Requirement: A bare marker is a violation, but prose is not
<!-- id: evc-04 -->
An unannotated `TODO`, `FIXME`, `XXX`, or `NotImplementedError` in a code position MUST
fail. The same words appearing inside explanatory prose or a rule definition MUST NOT
fail, because a gate whose signal-to-noise ratio is poor gets allowlisted into
uselessness — the exact failure `silent-success-scan.sh` exists to catch.

#### Scenario: real unfinished work
- **WHEN** a source line is a comment opening with `TODO:`
- **THEN** the gate fails naming the file and line

#### Scenario: documentation mentioning the word
- **WHEN** a comment describes marker handling without itself being a marker
- **THEN** the gate does not flag it

### Requirement: Exemptions are declared, not inferred
<!-- id: evc-05 -->
Paths exempt from the scan MUST be declared in an allowlist file. A fixtures directory
containing real backing data, or a test double tied to a live contract, MUST be exempted
explicitly rather than by heuristic.

#### Scenario: allowlisted fixtures
- **WHEN** a path matches a declared allowlist glob
- **THEN** markers within it are not counted

### Requirement: No files scanned is never a pass
<!-- id: evc-06 -->
When no files are scanned, the gate MUST exit with the nothing-scanned code.

#### Scenario: empty root
- **WHEN** the scan root contains no readable source files
- **THEN** the gate refuses with a vacuous-pass message

### Requirement: Evidence-claim scan exclusions are explicit and portable
<!-- id: evc-07 -->
The evidence-claim gate SHALL exclude version-control administrative metadata
by host-independent path component. Any intentional normative marker examples
exempted from scanning SHALL be listed by exact repository-relative path in
the existing evidence-claim allowlist with a file-specific rationale. All
other Markdown prose, fenced code, and source files SHALL remain subject to
the existing marker checks and nothing-scanned failure.

#### Scenario: generated Git metadata contains marker text
- **WHEN** the scanner encounters marker-shaped comments beneath a `.git`
  administrative directory on Windows or POSIX
- **THEN** those files are excluded by the `.git` path component and genuine
  repository files continue to be scanned

#### Scenario: reviewed normative examples are exempted
- **WHEN** a normative specification contains marker forms as intentional
  examples and its exact path is declared with rationale in the allowlist
- **THEN** that file is exempted while unrelated Markdown remains scanned

#### Scenario: a real marker occurs outside an exact exemption
- **WHEN** active marker text occurs in source, ordinary Markdown, or fenced
  Markdown code outside an allowlisted file
- **THEN** the gate fails and names the path and line
