# spec-status-disposition Specification

## Purpose
Records why a canonical capability is not yet in a proven terminal state and who owns the next evidence step, while keeping lifecycle status separate from audit notes.

## Requirements

### Requirement: Unknown specs have an explicit evidence disposition
<!-- id: spec-state-10 -->
Each canonical capability indexed UNKNOWN SHALL have a disposition for every requirement heading, or a stable heading reference when its ID is missing. Each disposition SHALL name its outcome, owner, evidence pointer or explicit absence, and review date. A disposition SHALL NOT change the lifecycle state or substitute for a state-ledger proof row.

#### Scenario: unreviewed unknown capability
- **WHEN** a canonical capability has no closure table or status
- **THEN** each requirement receives an explicit disposition and an owner or `unassigned` value, while its lifecycle state remains UNKNOWN until normal evidence rules are satisfied

#### Scenario: evidence is insufficient
- **WHEN** a disposition review finds only a source marker or unverifiable test reference
- **THEN** the outcome is `insufficient` and the capability is not reported CLOSED

### Requirement: External-owner disposition remains distinct from deferred lifecycle status
<!-- id: spec-state-11 -->
An evidence disposition SHALL identify an external owner and the awaited evidence when implementation belongs outside this repository. It SHALL NOT relabel a capability DEFERRED unless an explicit owner decision records that lifecycle state.

#### Scenario: external consumer owns implementation
- **WHEN** a capability is owned by a consuming repository but no evidence is supplied from that consumer
- **THEN** the disposition names the external owner and missing evidence without claiming closure or changing an existing DEFERRED decision
