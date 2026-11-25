# Proposal

## Why

Twelve canonical specs are UNKNOWN because they have no closure table or explicit status, even though their source-marker coverage varies from none to complete. The status index correctly avoids guessing, but consumers cannot distinguish owner-deferred, unverified, intentionally external, and simply unreviewed cases.

## What Changes

- Define an auditable disposition record for every UNKNOWN capability and every requirement under it.
- Record whether evidence is verified, missing, externally owned/deferred, or out of scope, with an owner and evidence pointer where known.
- Keep UNKNOWN or UNPROVEN where evidence is insufficient; disposition documentation does not itself close a requirement.
- Retain the existing DEFERRED game-type decision as owner-deferred and outside this UNKNOWN migration.

## Capabilities

### New Capabilities

- `spec-status-disposition`: explicit, evidence-linked disposition for canonical specs whose implementation state is not established.

### Modified Capabilities

None.

## Impact

OpenSpec status inventory, the twelve UNKNOWN specs, owner assignments, and audit report generation. No code capability is implied by a marker.
