# Qualify fleet boundary, contract and domain evidence

## Why

DG-02 rows 133-144 record historical claims with empty implementation citations. The three owning capabilities have current behavioral tests, but the twelve claims still need requirement-specific historical evidence and expected digests.

The `repo-004-01` consumer contract requires its fixture to catch both a missing path and an unsupported required reason code. In an extracted copy, adding a missing required path failed the contract suite. Adding a reason code outside the producer's v1 enum left all 24 tests passing. A core consumer could thus declare a minimum that the producer cannot satisfy without the suite reporting it.

## What Changes

- Check every reason code declared by the core consumer fixture against the producer. Exercise independent fixture changes for required paths and reason codes.
- Qualify the boundary gate in push CI, the remaining contract clauses and the model transitions against the published requirements.
- Bind historical proof and expected digests to each eligible claim before proposing a ledger transition.

## Impact

The follow-up covers the fleet boundary gate, v1 contract suite, desired-state model and DG-02 evidence review. The requirements already exist in the [boundary](../../specs/fleet-manager-boundary/spec.md), [contract](../../specs/fleet-manager-contracts/spec.md) and [domain](../../specs/fleet-manager-domain/spec.md) specifications. [Batch 012 evidence](../dg-02-evidence-ledger-reconciliation/batches/batch-012/README.md).
