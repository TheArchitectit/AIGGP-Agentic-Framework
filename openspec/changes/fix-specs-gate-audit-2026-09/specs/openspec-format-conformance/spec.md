## ADDED Requirements

### Requirement: published specs carry Purpose and Requirements

A published spec under `openspec/specs/<capability>/spec.md` SHALL have both a
`## Purpose` section and a `## Requirements` section, and every requirement
SHALL be a `### Requirement:` child of the `## Requirements` umbrella. A
level-2 `## Requirement:` heading is a *sibling* of the umbrella, not a child,
so it parses as zero requirements and fails validation — insertion of the
umbrella alone is not sufficient.

<!-- id: spec-fmt-01 -->

#### Scenario: umbrella without demotion

- **GIVEN** a spec with `## Requirements` inserted but requirements still at level 2
- **WHEN** `openspec validate <spec> --strict` runs
- **THEN** it fails reporting the spec must have at least one requirement

#### Scenario: missing purpose

- **GIVEN** a spec with a populated `## Requirements` section and no `## Purpose`
- **WHEN** `openspec validate <spec> --strict` runs
- **THEN** it fails naming the missing Purpose section

### Requirement: delta specs use the delta grammar

A change-package spec under `openspec/changes/<change>/specs/**/*.md` SHALL
declare its intent with a level-2 delta verb header (`## ADDED Requirements`,
`## MODIFIED Requirements`, `## REMOVED Requirements`, or
`## RENAMED Requirements`), and its requirements and scenarios SHALL use
`### Requirement:` and `#### Scenario:` respectively. A file written in the
published-spec shape is not a valid delta and fails validation. Normative verbs
SHALL be uppercase: the strict-mode check matches `SHALL` or `MUST` as whole
uppercase words, so a lowercase `shall` silently reads as an absent
requirement.

<!-- id: spec-fmt-02 -->

#### Scenario: published shape in a delta file

- **GIVEN** a change-package spec using `## Requirement:` and `### Scenario:`
- **WHEN** `openspec validate <change> --strict` runs
- **THEN** it fails reporting no delta sections found

#### Scenario: lowercase normative verb

- **GIVEN** a delta requirement whose obligation is stated with lowercase "shall"
- **WHEN** `openspec validate <change> --strict` runs
- **THEN** it fails reporting the requirement should contain SHALL or MUST

### Requirement: imported drafts carry no requirement identifiers

A package imported from an external program that has not started SHALL NOT
carry `<!-- id: -->` requirement markers, and SHALL declare its draft status in
its proposal. Requirement IDs drive the traceability gate, which counts an ID
as a tracked requirement and asks for a `// spec: <id>` marker in source; an ID
on an unimplemented draft therefore manufactures coverage for work that does
not exist.

<!-- id: spec-fmt-03 -->

#### Scenario: draft marked up as an active commitment

- **GIVEN** an imported draft package whose requirements carry ID markers
- **WHEN** `python3 scripts/spec_traceability.py --root .` runs
- **THEN** its requirements are counted as tracked and appear as uncovered
  obligations, as though the work were planned rather than merely drafted

### Requirement: strict validation is proven able to fail

The specs gate SHALL include a negative control that feeds a known-malformed
spec to `openspec validate --strict` and requires rejection. A gate whose only
evidence is that the current tree passes cannot distinguish a working validator
from one that accepts anything.

<!-- id: spec-fmt-04 -->

#### Scenario: validator accepts malformed input

- **GIVEN** a synthetic spec file with a requirement and no requirement header
- **WHEN** the negative control runs `openspec validate` against it under `--strict`
- **THEN** a zero exit status fails the control, because the gate was supposed
  to refuse that input
