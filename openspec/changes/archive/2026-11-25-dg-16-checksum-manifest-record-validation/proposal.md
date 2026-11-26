# Proposal

## Why

The release checksum verifier stores parsed records in a dictionary. Duplicate
paths overwrite earlier records, so a malformed duplicate followed by a valid
record can be accepted. This makes the manifest ambiguous and can hide an
invalid record even though the gate is intended to fail closed.

## What Changes

- Validate each manifest record's SHA-256 syntax before inserting it.
- Reject duplicate normalized paths, including duplicates with malformed
  earlier records.
- Add focused disposable-repository regression tests.

## Capabilities

### New Capabilities

- `release-checksum-manifest`: enforce unambiguous, well-formed checksum manifest records.

## Impact

`scripts/gen-checksums.py` and focused tests; generated manifest content and
tracked script selection are unchanged.
