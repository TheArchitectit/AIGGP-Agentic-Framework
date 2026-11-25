# Proposal: Review the GitLab backup/restore deferral

## Why

OI-003's historical deferred review date was 2026-11-22. On 2026-11-25, the owner confirmed a real backup/restore drill is optional operator acceptance after explicit GitLab adoption, not a prerequisite to ship GitLab support alongside GitHub. Preserve the real-restore prerequisite before any gate depends on an adopted instance, without implying that a live drill occurred.

## What Changes

- Append a `not-actionable` triage disposition recorded 2026-11-25, without replacing the historical row or inventing a renewed review date.
- Preserve GLF-10 as an open, adoption-triggered task before any gate depends on a selected instance.
- Preserve the requirement for a real restore drill before any gate depends on that instance; do not treat the synthetic validator/report as a completed drill.
- Do not request a backup, endpoint, access, external report, or change existing dates.

## Capabilities

### New Capabilities

- `gitlab-restore-deferral-review`: Records an owner decision on backup/restore readiness for the optional GitLab instance and preserves its activation prerequisite.

### Modified Capabilities

None.

## Impact

The OI-003 review package and append-only triage update. The live restore task remains open as adoption-triggered operator acceptance. It does not change GitLab support or the backup/restore implementation and makes no claim that a live restore drill has occurred.
