# Spec Delta

## MODIFIED Requirements

### Requirement: the contract grows from the failure registry
<!-- id: art-evolve-01 -->
Each art failure class that reaches a human SHALL be appended to the failure registry with a prevention rule. Where a class is not covered by an existing requirement of this contract, the contract SHALL be extended to cover it. The registry entry's prevention rule SHALL name the requirement that would have prevented the class, or SHALL propose a new one. When proof depends on a consuming title, the disposition SHALL name the consumer owner and provide a repository evidence reference, or mark that proof NOT_RUN; this repository SHALL NOT claim the external build outcome from local documentation alone. A human-only obligation with no enforcing code SHALL remain explicitly uncovered rather than receive a false source marker.

#### Scenario: a new failure class appears
- **GIVEN** a failure class not covered by any existing requirement here
- **WHEN** it is logged to the failure registry
- **THEN** a contract extension is required, and the registry entry names the gap until it lands

#### Scenario: a class already covered
- **GIVEN** a failure class that an existing requirement already prevents
- **WHEN** it is logged
- **THEN** the prevention rule cites that requirement and no contract change is required

#### Scenario: an external consumer is part of the claim
- **GIVEN** the failure disposition depends on a title or consumer outside this repository
- **WHEN** the disposition is recorded
- **THEN** it names the external owner and evidence location, or marks the external proof NOT_RUN without claiming the consumer outcome

#### Scenario: no code enforcement site exists
- **GIVEN** the contract obligation requires human judgment and no function enforces it
- **WHEN** traceability is reported
- **THEN** the requirement remains visibly uncovered and no unrelated source marker is added
