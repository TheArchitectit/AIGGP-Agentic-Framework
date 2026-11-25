# Spec Delta

## Purpose

Verify that the shipped release checksum manifest unambiguously covers the current tracked script inventory.

## ADDED Requirements

### Requirement: Checksum manifest records are unambiguous and well-formed
<!-- id: fw-ci-06 -->
The checksum verifier SHALL reject any manifest record whose digest is not
exactly 64 hexadecimal characters and SHALL reject repeated normalized paths
before records are inserted into the verification mapping.

#### Scenario: malformed digest is present
- **WHEN** a checksum record has a digest with invalid characters or length
- **THEN** verification fails and reports the malformed record

#### Scenario: duplicate normalized path is present
- **WHEN** two records normalize to the same tracked path
- **THEN** verification fails for the duplicate and does not silently replace
  any prior record; malformed digests also fail before insertion
