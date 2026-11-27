# Qualify agent channel, operations and boundary evidence

## Why

DG-02 batch 011 found that `Operation` validates parameter values while iterating, before it has checked every parameter name. In a synthetic operation, a permitted value was inspected before a later `command` name was rejected. A `command` paired with a non-string value produced a generic pair-type refusal without naming the forbidden parameter. The existing `fleet-005-01` requirement calls for rejecting forbidden names before reading values and naming the refusal.

All twelve historical records in the batch have empty citations and rejected provenance. Current tests and historical QA documents provide leads for review; the records still lack accepted requirement-specific historical bundles and expected digests. The channel tests use an injected deterministic signature-verifier double, and the channel and operation ledgers are in-memory components.

## What Changes

- Validate all parameter names before inspecting any parameter value, and test forbidden names at different positions and with malformed or instrumented values.
- Qualify the channel, operation receipt and repository boundary scenarios with appropriately scoped fixtures and independent evidence review.
- Establish reviewable historical provenance and validate requirement-specific bundles before any DG-02 lifecycle transition.

## Impact

Fleet-manager operation validation, channel and receipt qualification, boundary checks, and DG-02 evidence reconciliation. This proposal records follow-up work under existing requirements and makes no implementation, deployment or lifecycle-transition claim.
