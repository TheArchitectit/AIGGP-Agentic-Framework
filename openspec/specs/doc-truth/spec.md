# Spec: Documentation truth

## Purpose

Keep shipped documentation consistent with the artifacts and contracts it describes — version artifacts agree, and instructions respect the project-overlay boundary.

## Requirements

### Requirement: Version artifacts agree
<!-- id: doc-version-01 -->
VERSION, CHANGELOG.md, and git tags SHALL describe the same release history;
the release pipeline SHALL update every artifact it owns in one step.

#### Scenario: reconstructed history
- **WHEN** the change lands
- **THEN** VERSION equals the newest tag and CHANGELOG documents every tag

### Requirement: Instructions follow the overlay contract
<!-- id: doc-overlay-01 -->
No shipped documentation SHALL instruct a consumer to edit files inside the
DevGate submodule; customization instructions SHALL reference the
project-root `.guardrails/` overlay or the relevant contract file.

#### Scenario: custom rules
- **WHEN** a reader follows AGENTS.md to add a project rule
- **THEN** they create or edit `<project>/.guardrails/` files only

#### Scenario: stated rule counts
- **WHEN** docs state a rule count
- **THEN** the count equals the shipped rules file, or the count is not
  stated
