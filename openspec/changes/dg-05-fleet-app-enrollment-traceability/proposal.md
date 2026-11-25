# Proposal

## Why

All nine `fleet-app-*` IDs are uncovered by source markers although the enrollment script, workflow, and hermetic tests contain apparent evidence. Reconciliation needs a verified mapping from each contract row to its actual entry point, test, CI invocation, and sealed result, while distinguishing hermetic tests from live fleet behavior.

## What Changes

- Map each ID to its exact enforcing function/workflow step and behavioral test, including negative controls and CI invocation.
- Record NOT_RUN for live fleet outcomes unless a real run's signed evidence is available.
- Seal requirement-specific evidence records and verify an attestation against the configured signer set; markers are added only after the site is confirmed to enforce that requirement.
- No enrollment credentials, permissions, or runtime behavior change.

## Capabilities

### New Capabilities

- `fleet-app-enrollment-evidence`: records per-requirement verification for the existing enrollment capability.

### Modified Capabilities

None.

## Impact

Existing enrollment script, GitHub workflow, tests, CI, and a new auditable evidence mapping artifact.
