## Design principles

- Additive, never divergent: GitLab adds coverage; it changes no verdict.
- Thin forge layer: everything forge-specific lives behind the adapter interface.
- Same scripts, same images: both forges execute identical gate scripts on identical digest-pinned images.
- Discovery before dependency: an undocumented instance is not infrastructure.

## Locked decisions (carried from the September 19 package)

- Instance posture: tailnet-only, pinned version, backup tested before reliance.
- Runner standard: rootless podman, digest-pinned images, fail-closed registration, mirroring the GitHub fleet.
- Template shape: GitLab includes invoking the same gate scripts as the GitHub workflow templates, 1:1 across all five gates.
- Hub integration: forge adapter emitting AIGGP envelopes; forge identity is an envelope field.
- Parity drill: seeded-failure corpus run on both forges; identical findings required; drill is blocking in CI.

## Major components

1. Instance discovery and documentation runbook (Sprint 0).
2. GitLab runner standard + setup automation.
3. Mirrored CI templates (GitLab includes).
4. Forge adapter (webhooks, auth, API) behind the forge interface.
5. Parity-drill harness and seeded corpus.
6. Backup/restore verification drill.

## Trust boundaries

- The adapter is the only component that talks GitLab API; gate scripts never see forge credentials.
- Forge webhooks are unauthenticated input until verified against instance secrets.
- Instance admin credentials stay outside gate infrastructure entirely.
