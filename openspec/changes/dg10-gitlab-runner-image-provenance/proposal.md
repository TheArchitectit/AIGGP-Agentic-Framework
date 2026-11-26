# Proposal

All ten GitLab CI mirrors use a digest-pinned `ghcr.io/aiggp/devgate-runner` image, but this repository does not expose a build workflow or source-to-digest provenance record for it. A digest pins bytes but does not tell consumers which reviewed source, build permissions, and process produced them.

## What Changes

- Identify and review the authoritative image source and restricted build identity.
- Publish signed provenance binding reviewed source and build workflow identity to the digest used by all mirrors.
- Require offline signature validation against an approved trust key and identity binding; reject wrong digest/signer without claiming live image availability.
- Add mirror consistency preflight without requiring GitLab or registry access.

## Capabilities

### New Capabilities

- `gitlab-runner-image-provenance`: reviewable source, build identity, and digest provenance for GitLab CI runner images.

### Modified Capabilities

None.

## Impact

Image build/release metadata, `templates/gitlab-ci/*.yml`, and provenance preflight. Credentials and internal registry secrets are excluded.