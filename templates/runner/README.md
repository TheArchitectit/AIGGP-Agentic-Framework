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

That also installs `devgate-watchdog-<name>.timer` on the runner: the spoke
watches the **hub** back, failing its own unit if the hub stops monitoring — so
a dead hub is noticed by a machine that is still up. Check it with
`systemctl --user status devgate-watchdog-<name>`.

Units, env file, and heartbeat helper are all named per runner
(`devgate-hb-<name>`, `devgate-watchdog-<name>`, `devgate-imgcycle-<name>`,
`~/.config/containers/devgate-heartbeat-<name>.env`), so one host can enroll
several runners without a later enroll overwriting an earlier runner's token.
The earlier fixed-name units (`devgate-heartbeat.*`, `devgate-hub-watchdog.*`)
predate that and are retired for the runner being re-enrolled.

## The evaluator image on a runner host

The coherence gate **never pulls** (coh-rt-01): the bytes it executes must be
the ones the registry pins, not whatever the network serves at gate time. The
pinned image therefore has to be on the host *before* the job starts — a host
without it does not fail, it SKIPs the container phase and looks healthy.

`runner-enroll.sh` installs `devgate-imgcycle-<name>.timer` beside the
heartbeat, and that timer converges the local store on the **recorded**
identity (`image@digest` — never `:main`; a host holding a *newer* `:main`
build is not converged either). It is **installed by enroll and enabled by
provisioning**: an unprovisioned host gets the units on disk and no running
timer, because a timer that failed every cycle is noise that teaches operators
to ignore the one that matters.

### The store is a per-fleet decision, and it must be the job's store

A runner deployed from this standard is itself a container whose only volume is
`/_work` (see `self-hosted-runner.container`) — no podman socket, no container
storage mount. So podman on the host is **not** automatically the podman a job
sees, and converging into a store the gate cannot read is the failure this
whole mechanism exists to prevent. It is worth being blunt about it: the
cycler would report success and the gate would SKIP, on the same host, at the
same time. Pick one shape per fleet and make it true everywhere:

- **(a) podman inside the runner container.** Give the runner image podman and
  back `~/.local/share/containers` with a named volume. The job, the cycle and
  the image all live in that store; the cycle runs *in the container*, so do
  not enable the host-side timer for these hosts.
- **(b) socket-shared host storage.** Bind the host's rootless podman socket
  (and its storage) into the runner container. The host-side timer installed
  here is the right one: the job reaches the same store through the socket.

Either way the cycle is told which store to fill and **verifies it by asking
podman** (`--root <store> info`, compared as the directory the name denotes, so
a trailing slash is not a mismatch). A store it cannot confirm exits non-zero
rather than pulling into a guess.

### Provisioning a host

Add the three variables to the runner's environment file — the same
per-runner file the heartbeat reads (design D3.1: one file per runner) — then
run enroll again:

```bash
# ~/.config/containers/devgate-heartbeat-<name>.env  (mode 600)
COHERENCE_IMAGE=ghcr.io/thearchitectit/aiggp-agentic-framework/devgate-coherence
COHERENCE_IMAGE_MANIFEST_DIGEST=sha256:…     # container/execution-profiles.json
COHERENCE_PODMAN_STORE=/home/runner/.local/share/containers/storage
```

The store must be the **graph root**, and the way to get it right is to ask
podman for it rather than to guess a path — the cycler asks the same question
of the same binary, so the two agree by construction:

```bash
podman info --format '{{.Store.GraphRoot}}'    # as the runner user
```

Measured on rootless podman 6.1.1, that is
`~/.local/share/containers/storage`. It is deliberately **not**
`/run/user/<uid>/containers`, which is the *run* root — a different directory
that podman would happily turn into a second, empty store.

`image` and `image_manifest_digest` are the registry's, and the two must be
copied **together**: a digest that does not match the recorded one is the
S4 defect that once shipped an unpullable pin while CI was green. Enrollment
leaves these lines alone — they survive re-enrollment, which is what lets an
operator own them.

Verify with `systemctl --user status devgate-imgcycle-<name>`; the timer's exit
codes are specific on purpose, because each one has a different fix:

| Exit | Meaning | Fix |
| --- | --- | --- |
| 0 | converged — the recorded bytes are in this store | — |
| 1 | configuration error (unset, or a tag where a digest belongs) | the env file above |
| 2 | podman is not available | install/start podman on this host |
| 3 | the pinned ref could not be fetched | registry/network/auth |
| 4 | verification failed — the store does not hold the recorded bytes | re-pull; check for a stale local build |
| 5 | store mismatch — podman's graph root is not `COHERENCE_PODMAN_STORE` | edit the path |
| 6 | the configured store does not exist (refused to create a mount) | fix the mount |
| 7 | podman could not answer for the store | find out why podman is down |

A host's image state is also reported to the hub on every heartbeat
(`image_digest` / `image_reason`), so the fleet view shows which of these a host
is in — or `unknown` if it has never reported. **Null is unknown, never
healthy**: a host that cannot serve the pinned evaluator is not counted ready
to gate.

---

*Last Updated: 2026-09-14*

## Already have a fleet?

If you already have runners on a host and want to add the N+1th (shared
entrypoint, durability, submodule transport), see
[add-a-runner.md](add-a-runner.md).
