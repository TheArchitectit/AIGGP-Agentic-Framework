# Proposal

## Why

`docs/SUBMODULE_WIRING.md` forbids committed `.gitmodules` registration and requires CI to provision an ignored `.devgate/` checkout, pinned to a SHA for reproducibility. The reusable `drift-scan.yml` still relies on `submodules: true`; `specs.yml` and `text-integrity.yml` also fetch recursively and then execute `.devgate` scripts without provisioning an ignored in-tree checkout. A clean copy-in consumer following the documented contract therefore cannot satisfy these jobs' tooling prerequisite.

## What Changes

- Provision DevGate in the required in-tree `.devgate/` path at a consumer-owned immutable SHA for each affected reusable workflow: `drift-scan.yml`, `specs.yml`, and `text-integrity.yml`.
- Preflight the full SHA, checkout, each job's explicit required scripts/data, and root anchoring before gates run.
- Align setup comments and onboarding docs; test all three copy-in workflows without `.gitmodules`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-template-contract`: reusable workflows provision their own exact DevGate checkout and fail before gates if invalid.

## Impact

`templates/github-workflows/drift-scan.yml`, `templates/github-workflows/specs.yml`, `templates/github-workflows/text-integrity.yml`, workflow/bootstrap tests, and `docs/SUBMODULE_WIRING.md`. The consumer owns the pin; the checkout remains ignored. Preserve the workflows' existing permissions, action pins, Python/Node versions, history depth, and gate scope.
