# Spec Delta

## ADDED Requirements

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
