# requirement-id-inventory Specification

## Purpose
Keep the OpenSpec CLI and the repository's requirement ID inventory aligned,
and require a stable identity for every canonical requirement heading.

## Requirements

### Requirement: strict validation is proven able to fail
<!-- id: spec-fmt-04 -->
The specs gate SHALL include a negative control that feeds a known-malformed
spec to `openspec validate --strict` and requires rejection. A gate whose only
evidence is that the current tree passes cannot distinguish a working validator
from one that accepts anything.

#### Scenario: validator accepts malformed input
- **GIVEN** a synthetic spec file with a requirement and no requirement header
- **WHEN** the negative control runs `openspec validate` against it under `--strict`
- **THEN** a zero exit status fails the control, because the gate was supposed to refuse that input

### Requirement: Every canonical requirement heading has a stable identity
<!-- id: spec-fmt-05 -->
Every canonical `### Requirement:` heading SHALL have exactly one valid,
unique ID marker in its requirement block. The inventory comparison SHALL
reject missing, malformed, duplicate, or extra IDs and SHALL preserve existing
valid identities during repair.

#### Scenario: missing or malformed identity
- **WHEN** a canonical heading has no supported ID, or its ID is empty or an unsupported placeholder
- **THEN** CI reports the capability and heading and fails the completeness check

#### Scenario: valid identity is preserved
- **WHEN** a missing identity is repaired after reference search
- **THEN** every existing valid ID remains unchanged and the repaired heading receives one unique ID

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
