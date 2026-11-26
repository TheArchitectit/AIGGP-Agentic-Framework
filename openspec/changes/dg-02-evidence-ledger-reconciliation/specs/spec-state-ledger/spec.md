# Spec Delta

## ADDED Requirements

### Requirement: Unproven requirements receive an immutable evidence disposition
<!-- id: spec-state-12 -->
Every row in the unproven roster reviewed for reconciliation SHALL receive a separate disposition record identifying the requirement, reviewed evidence, each proof condition met or missing, reviewer, review time, and final decision. The report SHALL be sealed and content-addressed using the existing evidence validator. The disposition SHALL NOT itself alter lifecycle state or replace an append-only state-ledger transition.

#### Scenario: required evidence is missing
- **WHEN** a reviewed row lacks a valid sealed bundle, passing named test, resolvable commit bound, or changed enforcement location
- **THEN** the disposition names that missing condition, remains sealed, and the requirement stays UNPROVEN

#### Scenario: proof conditions are all met
- **WHEN** a row has all proof conditions accepted by the existing state gate and evidence validator
- **THEN** its report links to the evidence and any state change occurs only through a matching append-only ledger row and closure update

#### Scenario: roster tampering
- **WHEN** a disposition record or its evidence reference changes after sealing
- **THEN** evidence validation fails and the report cannot be accepted as a reconciliation result
