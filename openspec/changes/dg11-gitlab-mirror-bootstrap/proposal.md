# Proposal

## Why

The consumer contract in `docs/SUBMODULE_WIRING.md` prohibits committed `.gitmodules` registration and requires CI to provision an ignored `.devgate/` checkout itself. The GitLab drift mirror sets `GIT_SUBMODULE_STRATEGY: recursive`, then invokes `${DEVGATE_DIR:-.devgate}/scripts/...` without provisioning that directory, so a clean consumer without `.gitmodules` does not satisfy the mirror's prerequisite.

## What Changes

- Provision a consumer-owned DevGate checkout at the fixed `.devgate/` path in GitLab template jobs before any gate command.
- Require a full immutable SHA and verify checkout revision, required scripts, and root placement before running gates.
- Keep the copy-in integration independent of submodules; test on a clean synthetic GitLab project without `.gitmodules` and preserve the no-live-instance requirement for hermetic checks.

## Capabilities

### New Capabilities

- `gitlab-template-bootstrap`: consumers using a GitLab CI mirror get a verified DevGate checkout without a committed submodule.

### Modified Capabilities

None.

## Impact

`templates/gitlab-ci/*.gitlab-ci.yml`, template and bootstrap tests, and `docs/SUBMODULE_WIRING.md` / `docs/GITLAB-FORGE.md`. The consumer owns the reviewed SHA and any fetch credentials stay in GitLab's protected variable store; no live GitLab instance is required for local mirror tests.
