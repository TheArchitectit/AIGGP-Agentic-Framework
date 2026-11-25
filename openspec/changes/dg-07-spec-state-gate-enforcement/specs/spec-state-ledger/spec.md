# Spec Delta

## MODIFIED Requirements

### Requirement: Enforcement placement is stated honestly
<!-- id: spec-state-09 -->
The enforcement mechanism MUST be documented together with what it can and cannot prevent. Where the repository accepts direct pushes to its default branch without a pull-request gate, a push-time job MUST NOT be described as blocking a transition; it detects one that already landed. A local hook that can be bypassed MUST be documented as bypassable, with the auditing mechanism named. A reviewed enforcement disposition SHALL cite the workflow event and timing, local hook behavior, and remote default-branch protection evidence with inspection source and time, or explicitly record remote protection as UNKNOWN/NOT_RUN. The disposition SHALL distinguish prevention, after-the-fact detection, and unverified host policy.

#### Scenario: overclaimed enforcement
- **WHEN** documentation states that a transition cannot be made, but the wired mechanism runs only after the ref has moved
- **THEN** the claim is a defect and must be restated as detection

#### Scenario: reviewed remote protection
- **WHEN** the enforcement disposition claims a host-managed branch rule
- **THEN** it cites an authorized read-only readback, the target default branch, and inspection time

#### Scenario: host configuration is unavailable
- **WHEN** no authorized remote branch-protection evidence is available
- **THEN** the record states UNKNOWN/NOT_RUN and does not infer protection from local CI configuration

#### Scenario: local hook is bypassable
- **WHEN** a local hook is cited as prevention
- **THEN** the disposition names its bypass path and the independent audit that can detect a bypassed transition
