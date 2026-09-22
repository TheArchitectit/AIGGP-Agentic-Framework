# Spec: Deliberately malformed — negative control fixture

This file MUST NOT validate. It is the input to the specs-gate negative control
(`spec-fmt-04`), which proves `openspec validate --strict` can actually refuse
malformed material rather than merely observing that the real tree passes.

It is malformed in three independent ways, any one of which must be rejected:
no `## Purpose` section, no `## Requirements` umbrella, and a requirement-shaped
line that is not a `### Requirement:` header.

## Requirement: a heading the parser does not recognize as a requirement

This line looks like a requirement but sits at level 2, so it is not a child of
any `## Requirements` section — and there is no such section anyway.

#### Scenario: an orphaned scenario

- **WHEN** this fixture is validated
- **THEN** validation fails, and the control treats a success as a control failure
