# Spec Delta

## Purpose

DevGate provides scoped checks and non-authorizing evidence. Adopters need a verified contract linking evidence, immutable delivery artifacts and runtime readback across eligible execution lanes.

## ADDED Requirements

### Requirement: Promotion verifies evidence against the exact artifact and deployment target
<!-- id: deploy-evidence-promotion-01 -->
The adopter handoff SHALL verify the existing subject attestation and detached approval. It SHALL match the approved artifact identity and selected deployment target to runtime readback before reporting verified promotion.

#### Scenario: Verified candidate
- **WHEN** the existing attestation and approval verify and the selected deployment reports the approved artifact
- **THEN** the handoff records verified promotion with the referenced attestation, approval, deployment target and observed artifact identity

#### Scenario: Mismatched or missing evidence
- **WHEN** a required proof or the resulting deployment digest cannot be tied to the reviewed artifact
- **THEN** verified promotion evidence is rejected with its missing or mismatched field
