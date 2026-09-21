## ADDED Requirements

### Requirement: archive only after stabilization

Standalone repositories SHALL NOT be archived until all P0/P1 migration issues are closed, required consumers pass, the first unified release provenance verifies, and the stabilization period completes.

#### Scenario: red consumer at archive time

Given any required consumer still failing on the unified path, when archive approval runs, then archive SHALL be denied.

### Requirement: durable archive signpost

Each archived repository SHALL preserve history, tags, releases, issues, security records, and a prominent pointer to the unified repository and migration guide. Deletion is forbidden.

#### Scenario: old URL visited

Given a person opens an old repository URL after archive, then they SHALL see the archived state and an exact working link to the canonical AIGGP repository.

### Requirement: rollback checkpoints

Rollback SHALL be rehearsed from IMPORTED, DUAL-PROVEN, and CANONICAL states before the first unified release. The runbook SHALL restore repository writability, branch protection, CI requirements, release safety, and consumer routing without losing commits.

#### Scenario: unified CI produces false green

Given a P0 false-green defect found during stabilization, when rollback is invoked, then old required checks and canonical write routes SHALL be restored to the last verified predecessor state, and commits made after cutover SHALL remain preserved for later replay.
