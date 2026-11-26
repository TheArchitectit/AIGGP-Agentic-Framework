# Spec Delta

## Purpose

Record the owner's current backup/restore decision for optional GitLab adoption without weakening the prerequisite for any future dependent gate.

## ADDED Requirements

### Requirement: Restore review follows the selected-instance decision
<!-- id: glf-oi-003 -->
An OI-003 review SHALL state whether backup/restore work is dormant or activated in relation to the latest OI-001 adoption and instance decision. If activated, the record SHALL preserve a real backup restore drill as a prerequisite before any gate depends on that instance and SHALL distinguish synthetic validation from a completed live drill.

#### Scenario: owner reviews the restore deferral
- **WHEN** an authorized owner reviews OI-003 against the latest OI-001 decision
- **THEN** the record uses `not-actionable` until explicit adoption, keeps GLF-10 open, retains a real restore-drill prerequisite before any gate depends on the selected instance, and claims no live restore from synthetic evidence
