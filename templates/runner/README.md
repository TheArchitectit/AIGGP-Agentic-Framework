# Self-Hosted Runner Standard (ghcr.io + Podman/Docker)

DevGate's standard for producing CI evidence on your own hardware is: **the
official GitHub Actions runner image, deployed as a container**. This matches
the proven pattern from the example-service repo (runner `example-runner`,
online since 2026-09-03, executing that repo's full gate suite on every push).

## Overview

| Decision | Standard |
| --- | --- |
| Base image | **`ghcr.io/actions/actions-runner`** — the official GitHub-maintained, MIT-licensed runner image (latest tag 2.337.0 at time of writing). Pin a digest once validated. |
| Deployment | **Podman quadlet** (rootless systemd) or Docker equivalent — see [`self-hosted-runner.container`](self-hosted-runner.container). |
| Registration | One container per project, distinct `ContainerName` + `RUNNER_NAME` + `RUNNER_LABELS`. Registration token supplied via drop-in `.env`, never committed. |
| Durability | `CONFIGURED_ACTIONS_RUNNER_FILES_DIR=/_work/runner-config` + `DISABLE_AUTOMATIC_DEREGISTRATION=true` + a named `/_work` volume — restarts reuse the registration, no fresh token needed. |
| Fail-closed | Jobs targeting an unregistered label queue; there is no hosted-runner fallback. An empty runner is a visible outage, not a silent hosted run. |

## Why ghcr.io/actions/actions-runner

- **Official**: built and published by GitHub's `actions` org from
  [actions/runner](https://github.com/actions/runner/blob/main/images/Dockerfile).
- **Correct contract**: ships the runner agent, the container hooks, a docker
  CLI, and the standard registration env vars (`RUNNER_NAME`, `RUNNER_TOKEN`,
  `RUNNER_LABELS`, `RUNNER_SCOPE`, `REPO_URL`, `RUNNER_WORKDIR`,
  `CONFIGURED_ACTIONS_RUNNER_FILES_DIR`, `DISABLE_AUTOMATIC_DEREGISTRATION`,
  `EPHEMERAL`).
- **License**: MIT. No third-party runner forks needed.
- Third-party images (e.g. `myoung34/github-runner`, `cathehacker/ubuntu:act`)
  were considered and rejected as defaults: extra supply-chain surface, and
  `act`-toolchain images are not registerable runner agents at all.

## Quick start (podman)

1. Copy [`self-hosted-runner.container`](self-hosted-runner.container) to
   `~/.config/containers/systemd/<project>-runner.container` on the runner host.
2. Edit `REPO_URL`, `RUNNER_NAME`, and `RUNNER_LABELS` for your project.
3. Create the token drop-in (one-time registration token from your repo's
   **Settings → Actions → Runners → New self-hosted runner**):

   ```bash
   mkdir -p ~/.config/containers/systemd/<project>-runner.container.d
   printf 'Environment=RUNNER_TOKEN=%s\n' "<TOKEN>" \
     > ~/.config/containers/systemd/<project>-runner.container.d/token.env
   chmod 600 ~/.config/containers/systemd/<project>-runner.container.d/token.env
   ```

4. `systemctl --user daemon-reload && systemctl --user start <project>-runner`
5. Verify the runner shows **Idle** in your repo's Settings → Actions → Runners,
   and that its labels include your custom label (plus `self-hosted`, `Linux`,
   `X64`).
6. Enable linger so the user systemd instance survives logout:
   `loginctl enable-linger $USER`.

## Toolchain additions

Most DevGate gates need only **python3 + node + git + bash**, all present in
the official image (python3 is in ubuntu-noble; install nothing for the core
suite). If your project's gates need a compiler (e.g. Rust's `cargo`), build a
thin child image `FROM ghcr.io/actions/actions-runner:<tag>` and install the
toolchain — keep the base pinned and the additions additive. Reference
implementation: example-service's `ops/monitor-hub-runner/Containerfile` (adds rust
stable + rustfmt + clippy, gcc-12, cmake, ninja, python3-yaml).

## Binding workflows to your runner

Do not hardcode `ubuntu-latest`. DevGate is **host-repo aware**: when embedded
as `.devgate/`, `scripts/detect-host-ci.py` reads the host repo's own
`.github/workflows/*.yml` and reports the `runs-on:` labels and `schedule:`
crons already declared there (secrets-redacted). Workflows that should run on
your hardware target the label this runner registers — see
[`../github-workflows/drift-scan.yml`](../github-workflows/drift-scan.yml) for
the two-job pattern that resolves the label at runtime.

## Secrets hygiene (mandatory)

This repo is public. Every runner artifact here must stay free of:

- registration tokens (use drop-ins or `podman run --env` overrides)
- `secrets.*` values of any kind
- internal IPs, hostnames with credentials, URLs with embedded auth

`scripts/detect-host-ci.py` redacts token-shaped values before anything
reaches stdout; keep that guarantee in any template you add.

## Monitoring your runner fleet

A runner deployed from this standard can report to the **runner monitor hub** —
one small service that watches every registered runner for offline state,
stalled queues, red gates, and stale drift scans, and files a deduplicated
GitHub issue when something breaks. The hub ships in `hub/`; its image and
quadlet template are under
[`../runner-monitor/`](../runner-monitor/), and the deployment runbook
(volume, tokens, firewall, linger, enrollment) is
[`docs/runner-monitor-monitor-hub.md`](../../docs/runner-monitor-monitor-hub.md).

Enrolling a runner is one command on its host:

```bash
scripts/runner-enroll.sh <hub-url> <enrollment-token> --repo OWNER/REPO
```

That also installs `devgate-hub-watchdog.timer` on the runner: the spoke watches
the **hub** back, failing its own unit if the hub stops monitoring — so a dead
hub is noticed by a machine that is still up. Check it with
`systemctl --user status devgate-hub-watchdog`.

---

*Last Updated: 2026-09-14*
