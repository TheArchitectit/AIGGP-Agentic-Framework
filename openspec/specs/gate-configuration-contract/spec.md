# Spec: Gate configuration contract

## Purpose

Fix where gate configuration lives: a project customizes behavior through its own root-level overlay files rather than by editing the DevGate submodule.

## Requirements

### Requirement: Configuration lives in the project overlay
<!-- id: rule-config-01 -->
Every gate's project-specific configuration (detector families, allowlists,
schema contracts, scan scoping) SHALL be resolvable from the project-root
`.guardrails/` overlay and `.guardrailsignore`, merged over the bundled
baseline, without editing files inside the DevGate submodule.

#### Scenario: project allowlist entry
- **WHEN** a project's overlay allowlist covers a silent-success hit in the
  project's tree
- **THEN** the scan reports it allowlisted without any submodule edit

#### Scenario: schema contract file
- **WHEN** `<project>/.guardrails/schema-contract.json` declares an adapter
  and expected columns
- **THEN** schema-health-check validates against it and the shipped script is
  unmodified

### Requirement: Fresh installs are green
<!-- id: rule-fresh-01 -->
With no overlay present, every opt-in gate SHALL ship in its documented
disabled-by-default state and exit 0 with its skip notice.

#### Scenario: silent-success on a fresh install
- **WHEN** silent-success-scan runs on a fresh consumer with no overlay
- **THEN** it prints the no-families-enabled skip notice and exits 0
