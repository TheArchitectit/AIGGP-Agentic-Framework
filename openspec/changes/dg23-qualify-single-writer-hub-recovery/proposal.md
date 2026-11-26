# Qualify monitor single-writer restart and recovery

## Why

The monitor standard defines one hub and persistent instance state. The implementation uses a process-local lock and atomic file writes. Operators need verified recovery for that supported topology.

## What changes

Specify one supported active-writer deployment. Validate deployment inputs, independent backup contents, ownership handoff, recovery verification and behavior during unavailable or incompatible state.

## Capabilities

Add a requirement to the existing hub-architecture capability.

## Impact

The supported change applies to the repository-owned deployment or verification paths identified in the design. Authoritative adopter acceptance remains with the relevant service or release owner.
