# Spec Delta

## ADDED Requirements

### Requirement: owned YAML CI sources carry discoverable requirement markers
<!-- id: spec-fmt-06 -->
The shared requirement source inventory SHALL discover standalone `# spec:`
comments in `.yml` and `.yaml` files under `.github/workflows/`,
`templates/github-workflows/`, and `templates/gitlab-ci/`. It SHALL exclude
documentation, tests, fixtures, examples, generated content, and archives from
this YAML source class, and marker-shaped YAML scalar text SHALL NOT count as a
source marker. Both traceability and gap scanning SHALL use the same discovery
result.

#### Scenario: an owned YAML workflow marker is discovered
- **WHEN** an eligible CI source file contains a standalone marker for a known
  requirement
- **THEN** traceability and gap scanning both recognize that marker at the
  source path

#### Scenario: a YAML example or fixture is excluded
- **WHEN** an otherwise uncovered requirement appears only as a marker in
  documentation, test fixture, example, generated file, or archive
- **THEN** the source inventory leaves the requirement uncovered

#### Scenario: marker-shaped scalar text is ignored
- **WHEN** an eligible YAML file contains marker-shaped text inside a scalar
  value, including a standalone-looking indented line in a literal or folded
  block scalar
- **THEN** the source inventory excludes the payload marker and recognizes a
  genuine standalone comment after the scalar ends
