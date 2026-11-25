# Proposal

## Why

The published tree has eight requirement headings without parseable IDs, while strict OpenSpec validation passes and the marker gate silently omits them. The strings `<!-- id: -->` and `<!-- id: ... -->` are literal format examples in prose, not malformed requirement markers. The existing `spec-fmt-01` contract requires the tools to agree, so the audit gap should become an explicit, enforceable spec invariant.

## What Changes

- Require exactly one well-formed, unique ID for every canonical requirement heading and make the supported marker inventory agree with the strict OpenSpec inventory.
- Repair the eight missing IDs with durable, unique identities after checking for references.
- Add diagnostics and a CI gate comparison that fails on missing, malformed, duplicate, or divergent inventory entries.
- Do not add source bindings merely to increase coverage; bind only where an existing enforcement site is verified.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `spec-platform`: add the already-coded strict-validation negative control to the canonical contract and require complete, stable requirement identities across the CLI and marker inventory.

## Impact

`openspec/specs/` requirement headings, `scripts/lib/spec_discovery.py`, traceability/validation CI, and tests. Existing IDs must remain stable; malformed placeholders are not identities.
