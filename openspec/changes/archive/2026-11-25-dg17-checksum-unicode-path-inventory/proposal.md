# Proposal

## Why

`scripts/gen-checksums.py` reads `git ls-files` as line-oriented text. With Git's `core.quotePath=true`, a tracked Unicode path such as `scripts/r\u00e9sum\u00e9.py` is emitted as a quoted octal-escaped record. The current extension filter does not recognize that quoted line, so generation omits the script and verification can report success against the incomplete manifest. The existing line-oriented manifest also cannot encode every path without ambiguity: line breaks split records, backslashes have host-dependent meaning, and trailing whitespace is stripped by verification.

## What Changes

- Read tracked paths from NUL-delimited Git output and preserve valid UTF-8 names exactly, independent of `core.quotePath`.
- Detect supported tracked paths the current line-oriented manifest cannot encode, and fail clearly in both generate and verify modes before producing or accepting a partial inventory.
- Add disposable-Git regressions for Unicode inclusion, valid internal spaces, and unrepresentable path failures, including a noncandidate filename control.

## Capabilities

### New Capabilities

- `release-checksum-manifest`: preserve the complete supported tracked-script inventory in the shipped checksum manifest.

### Modified Capabilities

None. This capability is separate from `framework-ci` so it does not inherit the legacy terminal CI label.

## Impact

`scripts/gen-checksums.py`, focused checksum inventory tests, and `CHECKSUMS.sha256` if the final tracked script bytes change. This change preserves the current `scripts/` and `hub/` roots, supported extensions, SHA-256 format, and manifest ordering.
