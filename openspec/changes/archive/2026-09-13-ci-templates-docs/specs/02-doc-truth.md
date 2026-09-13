# Spec: Documentation truth

## Requirement: Version artifacts agree
<!-- id: doc-version-01 -->
VERSION, CHANGELOG.md, and git tags shall describe the same release history;
the release pipeline shall update every artifact it owns in one step.

#### Scenario: reconstructed history
- **WHEN** the change lands
- **THEN** VERSION equals the newest tag and CHANGELOG documents every tag

## Requirement: Instructions follow the overlay contract
<!-- id: doc-overlay-01 -->
No shipped documentation shall instruct a consumer to edit files inside the
DevGate submodule; customization instructions shall reference the
project-root `.guardrails/` overlay or the relevant contract file.

#### Scenario: custom rules
- **WHEN** a reader follows AGENTS.md to add a project rule
- **THEN** they create or edit `<project>/.guardrails/` files only

#### Scenario: stated rule counts
- **WHEN** docs state a rule count
- **THEN** the count equals the shipped rules file, or the count is not
  stated
