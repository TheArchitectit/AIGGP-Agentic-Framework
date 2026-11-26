# Spec Delta

## Purpose

Record owner decisions on the conditional live two-forge parity review while preserving the valid, narrower hermetic parity evidence.

## ADDED Requirements

### Requirement: Live parity readiness is reviewed conditionally
<!-- id: glf-oi-002 -->
A review of the OI-002 live parity deferral SHALL state its readiness in relation to the latest OI-001 owner decision. The record SHALL distinguish hermetic adapter-path parity from evidence run on two live forges and SHALL NOT claim live parity without such evidence.

#### Scenario: owner reviews the live parity deferral
- **WHEN** an authorized owner reviews OI-002 using the latest OI-001 decision
- **THEN** the record uses `not-actionable` for live parity until explicit adoption, keeps the live task open, preserves hermetic parity as required ship evidence, retains the hermetic-versus-live distinction, and makes no unsupported two-forge claim
