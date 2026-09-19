# Proposal: Add-runner-to-fleet walkthrough

## Problem

`templates/runner/README.md` documents first-provision only (one runner, one
repo). There is no walkthrough for adding the N+1th runner to a fleet that
already has runners, a shared entrypoint, and a monitor-hub. Operators who
follow the existing README for the N+1th runner will create a duplicate
entrypoint and miss the credential-pre-seed pattern that makes durability work.

## Solution

Add a new document `templates/runner/add-a-runner.md` covering:

1. **Reuse the shared entrypoint** — bind-mount, don't fork
2. **Token hygiene** — pipe raw `gh api` output, never through argv or shell
   history
3. **Submodule transport** — HTTPS default (zero credential needed for public
   repos); SSH fallback with per-repo deploy key for private repos
4. **Durability** — credential pre-seed pattern, the `EnvironmentFile=` must
   exist at start (podman constraint)
5. **Registration** — quadlet + drop-in pattern, `systemctl daemon-reload`,
   verification steps
6. **.gitignore note** — pointer to private infra repo for machine-specific
   details (hostnames, IPs, volumes)

The new file stays generic — role placeholders, no real hostnames/IPs/tokens —
per `mon-monitor-hub-01` and `mon-registry-01`.

## Affected specs

- New requirement: `fleet-add-01` — documented N+1th runner procedure
- Cites: `mon-monitor-hub-01`, `mon-registry-01`, `mon-enroll-01`

## .gitignore change

Add a commented block noting that machine-specific runner/fleet details are
deliberately out of scope and live in the operator's private infra repo.