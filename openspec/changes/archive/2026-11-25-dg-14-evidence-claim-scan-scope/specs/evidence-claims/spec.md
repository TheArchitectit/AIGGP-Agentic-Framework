# Spec Delta

## ADDED Requirements

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
