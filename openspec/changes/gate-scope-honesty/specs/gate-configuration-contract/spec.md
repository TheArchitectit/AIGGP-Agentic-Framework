# Gate Configuration Contract

## Purpose

Repositories already declare scan scope once, in `.guardrails/scope.json`
(fw-scope-01). A scanner with a hardcoded view of the world is a second,
contradicting contract; a scanner that accepts a declared view must say which
view it used.

## ADDED Requirements

### Requirement: A scanner's swept surface is declared in the scope contract
<!-- id: gate-anchor-scope-01 -->
For scanners with repo-class inventory anchors, projects SHALL be able to
override the anchors in `.guardrails/scope.json`. The scanner SHALL report the
anchor set it used. A missing file or key selects the built-in defaults. An
unparseable, empty or out-of-repository declaration (coh-sec-01) SHALL produce
a configuration error.

#### Scenario: a non-game-shaped repo declares its anchors

- **GIVEN** a repo whose code lives under `scripts/`
- **AND** `.guardrails/scope.json` declares `"inventory_dirs": ["scripts"]`
- **WHEN** `spec_gap_scan.py` runs over it
- **THEN** the inventory names capabilities from those files instead of
  exiting 2 for want of `src/autoload`
- **AND** the output records that the anchors came from `.guardrails/scope.json`

#### Scenario: an honest empty says whose scope it was

- **WHEN** declared anchor dirs contain no capability anchors
- **THEN** the "unknown scope" refusal (exit 2) names the declared dirs and
  says they came from the project's scope file, not from the built-ins

#### Scenario: a declared scope that escapes the repo

- **WHEN** `inventory_dirs` contains an absolute path or one containing `..`
- **THEN** the scanner exits 2 naming the refused entry
- **AND** it does not scan the escaped tree and it does not quietly use the
  built-in defaults
