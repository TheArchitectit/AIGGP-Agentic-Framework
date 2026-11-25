# Proposal

## Why

`art-evolve-01` governs a human failure-registry and contract-extension process and is intentionally uncovered; its guide explicitly rejects fake source bindings. To make the external boundary actionable, the contract must identify who owns consumer-dependent proof and what artifact is required before a class can be called covered.

## What Changes

- Extend `art-evolve-01` to require an owner and evidence pointer for external-consumer-dependent art failures.
- Require a real registry event and prevention mapping; external shipped-build claims must be evidenced by the consuming repository or marked NOT_RUN.
- Preserve intentional non-coverage when human judgment has no executable enforcement site.
- Do not invent an external consumer, class event, or local code binding.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `art-creation-contract`: extend the existing `the contract grows from the failure registry` requirement with external ownership and proof scope.

## Impact

Art contract, extension guide, failure registry, and evidence supplied by external game consumers.
