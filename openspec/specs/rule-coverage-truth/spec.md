# Rule coverage truth

## Purpose

Shipped rule data is real: every rule file that ships is loaded and enforced by a named gate, every declared rule is reachable by the scanners its file_glob names, and dead rulesets do not ship in the baseline.

## Requirements


### Requirement: Enabled means enforced
<!-- id: rule-truth-01 -->
Every rule shipped with `enabled: true` in any prevention-rules file SHALL
have an executing enforcement path in the corresponding gate; a hygiene check
SHALL fail when an enabled rule has no implementation.

#### Scenario: semantic rule without checker
- **WHEN** semantic-rules.json enables a rule id no registered checker
  implements
- **THEN** the rules-hygiene check fails naming the rule id

#### Scenario: documented coverage matches shipped coverage
- **WHEN** the README or a script header names a rule as enforced
- **THEN** that rule is enabled and has a registered checker

### Requirement: Behavior rules live in skills
<!-- id: rule-behavior-01 -->
Rules constraining agent behavior (git operations, destructive commands,
scope discipline) SHALL be published as skill-template content, not as
prevention-rules JSON that no file scanner can enforce.

#### Scenario: extracted-rules removal
- **WHEN** the change lands
- **THEN** extracted-rules.json is absent and the docs name the skill
  template covering each former rule

### Requirement: Language-aware spec markers
<!-- id: rule-marker-01 -->
The spec-traceability gate SHALL recognize requirement markers in each
scanned language's comment syntax (`//`, `#`, `--`), and scaffolding SHALL
instruct implementers in the target file's own syntax.

#### Scenario: Python marker
- **WHEN** a requirement id appears as `# spec: <id>` in a .py source file
- **THEN** the gate counts the requirement covered in blocking mode
