# Spec Delta

## MODIFIED Requirements

### Requirement: Enforcement placement is stated honestly
<!-- id: spec-state-09 -->
The enforcement disposition SHALL state the actual prevention or detection
role, workflow event and timing, and local hook behavior. Host-policy claims
SHALL cite the default branch, readback source, and observation time.
Unavailable host-policy evidence SHALL be recorded as UNKNOWN/NOT_RUN.

#### Scenario: overclaimed enforcement
- **WHEN** the repository accepts direct pushes to its default branch and the
  workflow runs after the ref moves
- **THEN** the disposition describes the workflow as detection after the push

#### Scenario: reviewed remote protection
- **WHEN** the enforcement disposition claims a host-managed branch rule
- **THEN** it cites an authorized read-only readback, the target default branch, and inspection time

#### Scenario: host configuration is unavailable
- **WHEN** no authorized remote branch-protection evidence is available
- **THEN** the record states UNKNOWN/NOT_RUN and does not infer protection from local CI configuration

#### Scenario: local hook is bypassable
- **WHEN** a local hook is cited as prevention
- **THEN** the disposition names its bypass path and the independent audit that can detect a bypassed transition
