# Proposal

## Why

`docs/SUBMODULE_WIRING.md` forbids committed `.gitmodules` registration and requires CI to provision an ignored `.devgate/` checkout, pinned to a SHA for reproducibility. The reusable `templates/github-workflows/drift-scan.yml` still tells consumers to use `submodules: true` and has no bootstrap step, so a clean consumer following the documented contract does not provide the scripts the job invokes.

## What Changes

- Provision DevGate in the required in-tree `.devgate/` path at a consumer-owned immutable SHA.
- Preflight the full SHA, checkout, required scripts, and root anchoring before gates run.
- Align setup comments and onboarding docs; test copy-in use without `.gitmodules`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-template-contract`: reusable workflows provision their own exact DevGate checkout and fail before gates if invalid.

## Impact

`templates/github-workflows/drift-scan.yml`, `tests/test_drift_scan_template.py`, and `docs/SUBMODULE_WIRING.md`. The consumer owns the pin; the checkout remains ignored.