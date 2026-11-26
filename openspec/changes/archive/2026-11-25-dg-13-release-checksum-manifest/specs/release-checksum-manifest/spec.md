# Spec Delta

## ADDED Requirements

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
