# Proposal

## Why

The index marks 42 specs (182 requirement rows) UNPROVEN because no sealed evidence ledger row substantiates terminal exercise. Existing rules forbid prose-only closure; reconciling those rows needs a complete, immutable proof disposition without fabricating missing evidence.

## What Changes

- Review each of the 182 rows against enforcement, behavior tests, changed-file history, resolved ordered commits, and the existing sealed evidence validator.
- Produce a sealed, content-addressed row-by-row disposition artifact. Append ledger transitions only where existing proof rules are satisfied; retain unresolved rows as UNPROVEN and identify missing evidence.
- Preserve the original unproven roster and ledger as append-only historical inputs.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `spec-state-ledger`: require an immutable, evidence-backed disposition for each reviewed unproven requirement without changing lifecycle state vocabulary or proof conditions.

## Impact

`openspec/state-unproven.jsonl`, `openspec/state-ledger.jsonl`, closure tables, sealed evidence validation, and index generation.
