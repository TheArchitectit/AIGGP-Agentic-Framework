# Release Checksum Manifest

## ADDED Requirements

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
