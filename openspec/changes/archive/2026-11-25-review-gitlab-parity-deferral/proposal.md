# Proposal: Review the live GitLab parity deferral

## Why

OI-002's historical deferred review date was 2026-11-22. On 2026-11-25, the owner confirmed that two-live-forge parity is optional operator acceptance after explicit GitLab adoption, not a prerequisite to ship GitLab support alongside GitHub. Hermetic template, adapter, and interoperability parity remains required and must be verified separately; this decision claims no live parity.

## What Changes

- Append a `not-actionable` triage disposition recorded 2026-11-25, without replacing the historical row or inventing a renewed review date.
- Preserve the live two-forge task as open and adoption-triggered; verify the hermetic parity test and CI invocation separately.
- Do not run a live drill, contact a forge, request external evidence, or presume that GitLab adoption has been approved.

## Capabilities

### New Capabilities

- `gitlab-parity-deferral-review`: Records an owner decision on the live two-forge parity deferral while preserving the scope of hermetic parity evidence.

### Modified Capabilities

None.

## Impact

The OI-002 review package and append-only triage update. The live two-forge item remains open as adoption-triggered operator acceptance. No parity implementation, CI behavior, corpus, or historical source date changes are included.
