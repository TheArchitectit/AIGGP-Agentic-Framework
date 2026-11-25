# Proposal: Review the GitLab instance deferral

## Why

OI-001's historical deferred review date was 2026-11-22. On 2026-11-25, the owner confirmed the product goal is to support GitLab alongside GitHub; selecting or enrolling a live instance is optional operator acceptance after explicit adoption, not a prerequisite to ship. Record that scope decision without implying a server was found or contacting an endpoint.

## What Changes

- Record the owner's confirmed product scope and the explicit adoption trigger; preserve the real-instance setup task as open.
- Append a `not-actionable` triage disposition recorded 2026-11-25, without replacing the historical row or inventing a renewed review date.
- Do not collect or publish private endpoints, aliases, credentials, or outside evidence.
- Keep the dormant Sprint 0 implementation in `add-gitlab-forge-support` unchanged.

## Capabilities

### New Capabilities

- `gitlab-instance-adoption-review`: Records an owner decision and authorized trigger for whether the optional GitLab instance work remains dormant or becomes active.

### Modified Capabilities

None.

## Impact

The OI-001 review package, append-only triage update, and owner decision record. The live product-scope row remains open as an adoption-triggered task. This does not run discovery, alter GitLab support, or claim a live instance exists.
