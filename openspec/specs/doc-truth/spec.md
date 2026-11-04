# Documentation truth

Status: Closed (2 of 2 requirements terminal 2026-11-03). `doc-version-01`:
VERSION equals the newest `v*` git tag, CHANGELOG.md documents exactly those
tags, `scripts/deploy.sh` writes VERSION and folds `[Unreleased]` in one step
at release time, and `scripts/check_version_truth.py` gates the agreement in
CI; the untagged `1.3.0` staging was folded into Unreleased (2026-11-03).
`doc-overlay-01`: live grep of AGENTS.md, README.md, and templates/ verified
no shipped documentation instructs editing inside the DevGate submodule;
customization instructions reference the project-root `.guardrails/` overlay.


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
