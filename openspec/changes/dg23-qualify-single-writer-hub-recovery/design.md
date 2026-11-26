# Qualify monitor single-writer restart and recovery

## Context

The monitor standard defines one hub and persistent instance state. The implementation uses a process-local lock and atomic file writes. Operators need verified recovery for that supported topology.

## Decisions

Keep the published Quadlet and registry contracts. Add supported topology validation to the operator entry point and name recoverable state and protected credential dependencies. Verify cold start and restored startup with synthetic data. Require a separate design for coordinated writers and fencing.

## Risk and verification

Overlapping hub processes could write inconsistent files, and incomplete backups can create a silent healthy instance with missing state. Verify preflight and restore readback alongside the existing independent watchdog.

## Rollout

Review the scenario matrix, exercise it with an isolated configuration, and record exact source and artifact identities before enabling the supported profile or recording acceptance.
