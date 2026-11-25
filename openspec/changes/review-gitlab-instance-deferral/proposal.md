# Proposal: Review the GitLab instance deferral

## Why

OI-001's deferred review date was 2026-11-22, and the aging gate now reports it expired. The existing record says GitLab remains an optional, dormant integration until adoption, so the owner must review the current adoption/instance decision without implying that a server was found or contacting an endpoint.

## What Changes

- Present the existing OI-001 ledger row, triage reason, and 2026-11-15 owner decision together for an authorized owner review.
- Record the owner's current choice to keep instance work dormant or activate it, together with the next authorized trigger.
- Preserve source and review dates; do not collect or publish private endpoints, aliases, credentials, or outside evidence.
- Keep the dormant Sprint 0 implementation in `add-gitlab-forge-support` unchanged.

## Capabilities

### New Capabilities

- `gitlab-instance-adoption-review`: Records an owner decision and authorized trigger for whether the optional GitLab instance work remains dormant or becomes active.

### Modified Capabilities

None.

## Impact

Only the OI-001 review package and its owner decision record. This does not run discovery, alter GitLab support, change the open-item ledger or triage dates, or claim a live instance exists.
