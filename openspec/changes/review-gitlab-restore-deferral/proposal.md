# Proposal: Review the GitLab backup/restore deferral

## Why

OI-003's deferred review date was 2026-11-22, and its triage entry says it is blocked on OI-001 because no instance exists to back up. The main GitLab change's later owner decision describes the live work as dormant until adoption, so the owner should reconcile the current restore-review status while preserving the restore-proof requirement before any gate depends on an adopted instance.

## What Changes

- Present OI-003's ledger and triage records with the current OI-001 owner decision for an authorized owner review.
- Record whether backup/restore remains dormant or is activated for an explicitly selected instance.
- Preserve the requirement for a real restore drill before any gate depends on that instance; do not treat the synthetic validator/report as a completed drill.
- Do not request a backup, endpoint, access, external report, or change existing dates.

## Capabilities

### New Capabilities

- `gitlab-restore-deferral-review`: Records an owner decision on backup/restore readiness for the optional GitLab instance and preserves its activation prerequisite.

### Modified Capabilities

None.

## Impact

Only the OI-003 review package and its owner decision record. It does not change GitLab support or the backup/restore implementation and makes no claim that a live restore drill has occurred.
