# Consume detached review receipts for exact corruption ranges

## Why

Permit a trusted reviewer to approve a precisely identified committed range that has known substitution-flip or mass-rewrite findings, without allowing the scanned repository to approve its own findings or suppressing unrelated findings.

## What Changes

- Add an opt-in range review interface that receives a detached, externally supplied review document and its authority-supplied SHA-256 digest.
- Bind any recognized review to the canonical repository identity, a full base commit, the exact target Git tree, and the complete inventory of substitution and mass-rewrite findings.
- Keep full-tree corruption scanning, staged scanning, control glyph checks, and control tests outside this review mechanism.

## Impact

The corruption range scanner and its tests. Existing callers without exact-review mode retain their current behavior; exact-review consumers scan without consumer-controlled range suppressions.
