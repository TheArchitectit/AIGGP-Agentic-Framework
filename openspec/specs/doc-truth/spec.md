# Documentation truth

Status: Closed (2 of 2 requirements terminal 2026-10-14). `doc-version-01`:
the version-artifact disagreement is resolved by the recorded version-truth
statement in CHANGELOG `[Unreleased]` (landed `0a26e37a`, 2026-10-13) —
VERSION=1.3.0 and newest tag v1.2.0 intentionally disagree until the next
tagged release, and that intent is the recorded truth per the owner-approved
B22 disposition; no retroactive tag. `doc-overlay-01`: live grep of AGENTS.md,
README.md, and templates/ verified no shipped documentation instructs editing
inside the DevGate submodule; customization instructions reference the
project-root `.guardrails/` overlay.


## Purpose

Keep shipped documentation consistent with the artifacts and contracts it describes — version artifacts agree, and instructions respect the project-overlay boundary.

## Requirements

Documentation equals the tree. Rule counts, script inventories, file names, and feature claims in README, AGENTS.md, templates, and CHANGELOG must match the files that actually ship; a doc that describes a smaller or older repo is a defect, not a nitpick.




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
