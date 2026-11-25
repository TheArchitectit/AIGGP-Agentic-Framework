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

### Requirement: The checksum inventory preserves supported Git paths
<!-- id: fw-ci-07 -->
The checksum generator and verifier SHALL enumerate supported tracked scripts from NUL-delimited Git path records, preserve valid UTF-8 names exactly, and fail closed before generation or verification when a supported path is invalid UTF-8, duplicated in the Git index, or cannot be represented by the line-oriented checksum manifest. An inventory error SHALL NOT produce or accept a partial manifest.

#### Scenario: a quoted Unicode path is included
- **WHEN** Git tracks supported ordinary and Unicode script paths while `core.quotePath` is enabled
- **THEN** generation emits one record for each exact path and verification accepts the complete inventory

#### Scenario: a pathname cannot be represented by the manifest
- **WHEN** a supported tracked script path contains a separator recognized by Python `str.splitlines()`, a backslash, or invalid UTF-8 bytes
- **THEN** both generate and verify fail with an actionable inventory error, generation leaves any existing manifest unchanged, and neither mode reports success for a partial inventory

#### Scenario: an unresolved index repeats a path
- **WHEN** Git reports the same supported path at multiple index stages
- **THEN** both generate and verify reject the duplicate path before reading or writing the manifest

#### Scenario: the supported inventory remains scoped
- **WHEN** the repository contains tracked files outside the supported `scripts/` and `hub/` roots or with unsupported final extensions
- **THEN** those files remain outside the checksum inventory

## Requirement Closure

| Requirement | Status | Implementation | Verification |
|---|---|---|---|
| `fw-ci-06` (Checksum manifest records are unambiguous and well-formed) | **WIRED** | `scripts/gen-checksums.py` | `tests/test_gen_checksums.py` |
| `fw-ci-05` (The shipped script checksum manifest matches tracked scripts) | **WIRED** | `scripts/gen-checksums.py`, `.github/workflows/ci.yml` | Hosted release-checksum step |
| `fw-ci-07` (The checksum inventory preserves supported Git paths) | **WIRED** | `scripts/gen-checksums.py` | `tests/test_gen_checksums.py` and hosted checksum step |
