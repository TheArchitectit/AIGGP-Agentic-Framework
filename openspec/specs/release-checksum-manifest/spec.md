# release-checksum-manifest Specification

## Purpose
Verify that the shipped release checksum manifest unambiguously covers the current tracked script inventory.

## Requirements

### Requirement: Checksum manifest records are unambiguous and well-formed
<!-- id: fw-ci-06 -->
The checksum verifier SHALL reject any manifest record whose digest is not
exactly 64 hexadecimal characters and SHALL reject repeated normalized paths
before records are inserted into the verification mapping.

#### Scenario: malformed digest is present
- **WHEN** a checksum record has a digest with invalid characters or length
- **THEN** verification fails and reports the malformed record

#### Scenario: duplicate normalized path is present
- **WHEN** two records normalize to the same tracked path
- **THEN** verification fails for the duplicate and does not silently replace
  any prior record; malformed digests also fail before insertion

### Requirement: The shipped script checksum manifest matches tracked scripts
<!-- id: fw-ci-05 -->
The checked-in `CHECKSUMS.sha256` SHALL contain a current SHA-256 digest for
every supported tracked script under `scripts/`, `hub/`, and no entry for an
untracked or removed script. The blocking CI verifier SHALL reject missing,
stale, and extra entries. Duplicate and malformed-record validation is
specified separately by `fw-ci-06`.

#### Scenario: a tracked script is added or changed
- **WHEN** a delivered change adds a supported tracked script or changes its
  bytes
- **THEN** the manifest is regenerated for the final tracked tree and the CI
  verifier accepts every script digest

#### Scenario: the manifest is stale or incomplete
- **WHEN** a tracked script is missing from the manifest or its digest differs
- **THEN** the CI verifier fails and identifies the affected path

#### Scenario: CI verifier reports the underlying manifest mismatch
- **WHEN** the release-checksum verifier fails under Bash `errexit`
- **THEN** CI preserves and prints the verifier's path-specific diagnostic
  before returning a failing status

## Requirement Closure

| Requirement | Status | Implementation | Verification |
|---|---|---|---|
| `fw-ci-06` (Checksum manifest records are unambiguous and well-formed) | **WIRED** | `scripts/gen-checksums.py` | `tests/test_gen_checksums.py` |
| `fw-ci-05` (The shipped script checksum manifest matches tracked scripts) | **WIRED** | `scripts/gen-checksums.py`, `.github/workflows/ci.yml` | Hosted release-checksum step |
