## ADDED Requirements

### Requirement: Approved main releases have immutable evidence
<!-- id: release-main-coverage-01 -->
A product release SHALL have an owner-approved version and changelog entry.
Its annotated release tag and published release SHALL identify the same
reviewed main commit. Release rehearsal SHALL run in isolated repositories.

#### Scenario: The existing workflow verifies a matching release
- **WHEN** VERSION identifies an annotated tag at the checked-out product commit and the changelog contains its release heading
- **THEN** the coverage step accepts the commit

#### Scenario: Main and release metadata disagree
- **WHEN** a product commit lacks a matching annotated tag or changelog heading
- **THEN** the coverage step fails with the reason for the mismatch

#### Scenario: Generated reports are the entire change
- **WHEN** a sweep push changes only eligible generated report paths
- **THEN** the coverage step reports its generated-report skip
- **AND** a mixed generated-and-product push remains subject to release coverage

#### Scenario: Local release rehearsal
- **WHEN** a reviewer runs the coverage fixture
- **THEN** each synthetic release tag stays in its disposable repository and existing release refs and metadata are preserved
