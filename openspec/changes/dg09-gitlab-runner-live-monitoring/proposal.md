# Proposal

## Why

AIGGP’s GitLab option ships enrollment metadata, forge adapters, and hermetic parity tests, but the hub monitor polls GitHub Actions APIs only. The owner decided 2026-11-15 that GitLab live proof is dormant until operator adoption; after activation, GitLab runners need matching live monitoring instead of being treated as monitored through GitHub endpoints.

## What Changes

- Preserve the optional, fixture-tested status; do not require a live instance before adoption.
- After explicit adoption, route GitLab health, queue, gate-result, and drift checks through GitLab APIs; report unsupported classes explicitly.
- Add adapter tests and conditional live acceptance without storing private instance details in git.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runner-monitoring`: live GitLab monitoring activates only after operator declaration and uses the declared forge adapter.

## Impact

`hub/monitor.py`, `hub/forge/monitor.py`, forge API/adapter and registry integration, tests. Instance URLs, tokens, and owner identities remain in approved operator configuration. Link the existing dormant parity and runner portability packages rather than duplicating them.