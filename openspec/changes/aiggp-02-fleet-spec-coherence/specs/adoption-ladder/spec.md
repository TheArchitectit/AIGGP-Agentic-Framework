## ADDED Requirements

### Requirement: centrally enforced minimums

Policy minimums SHALL be set outside repositories. A repository MAY tighten minimums and SHALL NOT loosen them.

#### Scenario: lower severity locally

Given a repo attempting to set a lower coherence floor than the central minimum, when policy resolution runs, then the attempt SHALL be rejected.

### Requirement: bounded advisory stage

Advisory stages SHALL have bounded duration. An advisory stage exceeding its bound SHALL escalate per policy (ratchet or waiver), never drift indefinitely.

#### Scenario: advisory expiry

Given a repo in Stage 1 past its bound with no waiver, when the ladder evaluator runs, then it SHALL report the expiry and apply the policy escalation.

### Requirement: no-regression ratchet

Once a repo ratchets to a baseline, new violations SHALL block even when pre-existing violations are baselined.

#### Scenario: four existing and one new violation

Given four baselined violations and one new violation, when evaluation runs at Stage 2+, then the verdict SHALL be FAIL citing only the new violation.
