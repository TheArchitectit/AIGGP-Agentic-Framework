# Proposal

## Why

The push-time workflow correctly describes itself as detection after the ref moves, and the local pre-commit hook is bypassable. The actual owner-managed branch protection state is not in the code checkout, so an honest enforcement assessment needs a reviewed evidence record that links local timing to a dated remote readback or explicitly records NOT_RUN.

## What Changes

- Extend `spec-state-09` to require a reviewer-attested comparison of workflow trigger/timing, local hook bypassability, and remote branch-protection state.
- Require remote state to cite an authorized read-only source and timestamp, or remain UNKNOWN/NOT_RUN where access is unavailable.
- Preserve detection/prevention distinctions and do not change any remote protection, hook, or workflow behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `spec-state-ledger`: add evidence-record requirements to `Enforcement placement is stated honestly`.

## Impact

`.github/workflows/spec-state.yml`, `scripts/hooks/pre-commit`, OpenSpec state documentation, and owner-controlled branch-protection configuration.
