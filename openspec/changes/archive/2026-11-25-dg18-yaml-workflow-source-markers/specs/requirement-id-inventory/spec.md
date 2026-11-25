# Spec Delta

## ADDED Requirements

### Requirement: Owned YAML workflow preambles carry discoverable requirement markers
<!-- id: spec-fmt-06 -->
The shared requirement source inventory SHALL read top-level standalone
`# spec:` comments only from the leading preamble of `.yml` and `.yaml` files
under `.github/workflows/`, `templates/github-workflows/`, and
`templates/gitlab-ci/`. The preamble ends at the first YAML content line.
Documentation, tests, fixtures, examples, generated content, archives, and
symlinked YAML files SHALL be excluded. Traceability and gap scanning SHALL
share the discovery result.

#### Scenario: an owned YAML workflow declares a source marker
- **WHEN** an eligible workflow includes a top-level marker before its YAML content
- **THEN** traceability and gap scanning both recognize that marker at the source path

#### Scenario: a YAML example or fixture is excluded
- **WHEN** an otherwise uncovered requirement appears only as a marker in an
  excluded path or a symlinked YAML file
- **THEN** the source inventory leaves the requirement uncovered

#### Scenario: marker-shaped YAML values are excluded
- **WHEN** marker-shaped text occurs after the preamble in quoted, literal,
  folded, or root scalar content
- **THEN** the source inventory leaves each scalar-only requirement uncovered
