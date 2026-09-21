## ADDED Requirements

### Requirement: escape-fixture conformance

Each level SHALL certify against a public escape-fixture suite covering filesystem, network, process-namespace, and secret-access escape attempts. Any successful escape SHALL revoke the level's certification for that runtime version.

#### Scenario: network escape succeeds

Given a fixture that reaches a forbidden endpoint, when the suite runs, then the level SHALL be reported non-conformant for that runtime version with the fixture named.

### Requirement: isolation in evidence

Every evidence envelope SHALL carry the workload's isolation level and the enforcing runtime's identity and version.

#### Scenario: missing level field

Given an envelope without isolation level, when validated, then it SHALL be rejected.
