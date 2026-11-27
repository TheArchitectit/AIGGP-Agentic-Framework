# Qualify spec, 3D and fleet-manager evidence gaps

## Why

DG-02 batch 010 found that the fleet adapter contract checker accepts synthetic adapters whose required `digest` or `registration_ref` name is a catch-all keyword parameter. The existing `fleet-007-01` requirement explicitly excludes catch-all parameters from satisfying required names.

Five reviewed fleet-manager rows have rejected provenance because the historical records cite no implementation path. The current synthetic 3D and fleet tests provide useful present-day evidence, but the records lack accepted requirement-specific historical bundles. Spec-platform archive and stacked-change scenarios also need direct lifecycle evidence.

## What Changes

- Make adapter signature validation reject catch-all parameters used as required named parameters and test every required name and relevant parameter kind.
- Qualify spec-platform archive, publication and stacked-change behavior, and maintain per-capability CLI/marker agreement checks.
- Establish evidence for the exact 3D decision, promotion and capture contracts and for the fleet adapter and agent-channel scenarios. Preserve empty historical citations as rejected until supported provenance is established through the evidence process.

## Impact

Fleet-manager adapter validation and tests, spec-platform and 3D qualification fixtures, and DG-02 evidence reconciliation. This change proposes work under existing requirements; it makes no deployment or lifecycle-transition claim.
