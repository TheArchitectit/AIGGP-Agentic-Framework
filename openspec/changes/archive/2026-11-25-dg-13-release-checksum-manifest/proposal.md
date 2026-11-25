# Proposal

## Why

The CI run for PR #41 failed in the release-checksum step. The branch changes
`scripts/check_exec_bits.py` and adds `scripts/spec_id_inventory.py`, while
`CHECKSUMS.sha256` still holds the prior digest for the former and has no entry
for the latter. The existing verifier correctly rejected the drift.

## What Changes

- Regenerate the checked-in checksum manifest from the final tracked script
  inventory after the branch's script changes are settled.
- Preserve the existing blocking CI verification and document the manifest's
  one-entry-per-tracked-script contract.
- Verify the generated manifest with the same verifier CI runs.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `release-checksum-manifest`: require the checked-in release checksum manifest to cover
  every supported tracked script with its current SHA-256 digest.

## Impact

`CHECKSUMS.sha256`, `scripts/gen-checksums.py`, and the existing release
checksum step in `.github/workflows/ci.yml`.
