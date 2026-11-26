# Spec Delta

## Purpose

Keeps historical OpenSpec task records immutable while exposing evidence-backed dispositions and any real successor work in a current reviewable inventory.

## ADDED Requirements

### Requirement: Archived tasks receive separate evidence-backed dispositions
<!-- id: spec-state-13 -->
Every archived task left unchecked, and every archived delta without an identifiable canonical successor, SHALL receive a stable reconciliation ID and a separate disposition record. The record SHALL include archive path, original task text and checkbox state, disposition, evidence pointer or explicit absence, and rationale.

#### Scenario: unchecked archive task
- **WHEN** a task remains unchecked in an archived change
- **THEN** its original checkbox remains unchanged and a separate disposition record states whether it is still open, deferred, retired, superseded, implemented, or unsubstantiated

#### Scenario: checked task lacks code evidence
- **WHEN** an archived task is checked but no current implementation or verification evidence is found
- **THEN** the reconciliation does not label it implemented solely from the checkbox

### Requirement: Live archived work is carried forward without false completion
<!-- id: spec-state-14 -->
A task disposition of still-open SHALL identify an owner and a successor active task with a new stable ID. The successor SHALL preserve the historical task text and SHALL NOT mark the archived task complete.

#### Scenario: genuinely outstanding work
- **WHEN** reconciliation establishes that an archived task remains necessary and undone
- **THEN** a new active task references its reconciliation ID and the historical archive remains unchanged
