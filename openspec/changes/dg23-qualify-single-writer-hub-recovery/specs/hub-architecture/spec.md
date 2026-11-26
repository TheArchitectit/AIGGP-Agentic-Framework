# Spec Delta

## Purpose

The monitor standard defines one hub and persistent instance state. The implementation uses a process-local lock and atomic file writes. Operators need verified recovery for that supported topology.

## ADDED Requirements

### Requirement: Monitor deployment preserves a single writer and recoverable state
<!-- id: mon-hub-recovery-01 -->
The supported monitor topology SHALL have one active writer. Deployment and restore SHALL reject inconsistent ownership or required state before emitting healthy recovery evidence.

#### Scenario: Supported restore
- **WHEN** the operator restores a verified snapshot into the supported single-writer topology
- **THEN** the monitor verifies and reports the restored state before returning healthy evidence

#### Scenario: Out-of-contract recovery
- **WHEN** a selected configuration requests overlapping active writers or a restore lacks required state
- **THEN** preflight denies the configuration or restore and identifies the failed condition
