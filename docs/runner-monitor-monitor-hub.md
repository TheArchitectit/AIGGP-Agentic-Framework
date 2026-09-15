# Runner Monitor — monitor-hub Deployment Runbook

> The gate suite that must pass before a hub goes live, and the steps that must
> happen **on the monitor-hub machine** because they involve secrets.
>
> **Nothing in this repository is a secret.** Every token below is minted on
> the hub machine, written to a `chmod 600` file, and never committed. This
> repo is public; treat a committed token as a leaked token.

## Overview

The runner monitor is a **hub-and-spoke** service. One small stdlib-only
Python hub runs on a single host — the *monitor-hub machine* — and every DevGate
self-hosted runner *reports to it*. No runner connects to any other runner.

`monitor-hub` is the role, not a hostname: the shipped quadlet and examples use
it wherever a real host or alias belongs. Substitute your own machine's name
and address as you deploy.

There are two independent evidence channels (`mon-channels-01`):

| Channel | Direction | Detects |
| --- | --- | --- |
| **GitHub API polling** | hub → GitHub REST | runner offline, stalled queue, red gate on a watched branch, overdue drift scan |
| **Spoke heartbeats** | runner → hub `/heartbeat` | spoke stale past two heartbeat intervals, disk/podman unhealthy |

Either channel alone is sufficient. A repo whose runner has never sent a
heartbeat is still watched API-side (`mon-channels-01`, "unenrolled runner
still watched").

**What ships in this repo:** hub source (`hub/`), its Containerfile + quadlet
template (`templates/runner-monitor/`), `scripts/runner-enroll.sh`, the
registry JSON schema + a redacted example, tests, and this runbook.

**What happens only on the hub machine:** the volume, the GitHub PAT, the
enrollment tokens, the listen port and firewall rule, linger, and starting the
quadlet. That is the whole point of `mon-monitor-hub-01`: a bare hub machine
plus this runbook must be enough, with no step reading a secret from the repo.

## Quick Reference

| # | Step | Where | Failure means |
| --- | --- | --- | --- |
| 1 | Build the hub image; pin the base digest | hub machine | Abort; nothing is running yet |
| 2 | Create the persistent volume | hub machine | Registry + alert log vanish on recreate — re-enrollment needed |
| 3 | Mint the fine-grained PAT → `chmod 600` drop-in | hub machine | Hub polls with no auth: every check 401s, alerts never fire |
| 4 | Mint enrollment tokens → `chmod 600` drop-in | hub machine | No runner can enroll (`401 unknown_or_revoked_token`) |
| 5 | Choose the listen port; add the firewall rule for **that port only** | hub machine | Hub reachable from anywhere, or not at all |
| 6 | `loginctl enable-linger $USER` | hub machine | Hub dies at logout; heartbeats stop being collected |
| 7 | Install the quadlet, `daemon-reload`, start | hub machine | Hub absent; dead-man switch (step 8) is your only signal |
| 8 | Verify `/health`; enable the dead-man workflow | hub machine + repo | A silently dead hub looks identical to a quiet fleet |
| 9 | Enroll each spoke with `runner-enroll.sh` | spoke machine | Runner invisible to the hub until it heartbeats |

## Why each step exists

### Secrets hygiene — `mon-registry-01`

`runners.json` and `alerts/*.jsonl` are **instance state**. They live on the
hub's volume and are never committed; the repo carries only the schema
(`hub/schema/runners.schema.json`) and a placeholder example. No committed file
may contain host IPs, credentialed hostnames, tokens, or live runner data.

The `.gitignore` already blocks the common accidents:

```
runners.json
alerts/*.jsonl
.devgate-heartbeat.env
```

That is a backstop, not a license: the token files below live outside the repo
(`~/.config/containers/systemd/…`, `$HOME/.devgate-heartbeat.env`) precisely so
no `git add` can reach them.

### Firewall — explicit bind, never `0.0.0.0` by default

`hub/config.py` defaults `bind_host` to **`127.0.0.1`**. The quadlet
deliberately overrides this to `0.0.0.0` *inside the container* and publishes
the port, because the container's network namespace is not the host's — the
host firewall is what actually restricts access. Open the hub port to enrolled
runner hosts only. Do not expose it to the internet.

### No TLS in-repo — bind to a private network

The hub's endpoints are **plain HTTP**, and `runner-enroll.sh` posts bearer
tokens over that connection. There is no TLS in this repository. That is
acceptable **only** on a private network you control (e.g. a tailnet or an
isolated LAN segment) — the firewall rule above is what makes it acceptable,
not the protocol.

Before you expose the hub beyond such a network, terminate TLS in front of it
(a reverse proxy with a real certificate) and point every spoke's `--hub-url`
at the `https://` endpoint. A bearer token sent over plain HTTP on an untrusted
segment is sniffable and replayable; this is a deployment decision the runbook
cannot make for you.

### Tokens are stored plaintext on the volume

`runners.json` holds heartbeat token values as written — the hub compares
against them with `hmac.compare_digest` but does not hash them at rest. This is
instance state on the hub volume, never committed (`mon-registry-01` honored),
so the exposure is bounded by who can read that volume. If that boundary is too
wide for you — root on the hub host, a volume backup that leaves the machine,
a shared storage backend — that is the reason to tighten it. Hashing at rest
would cut the blast radius of a volume read; it is not implemented in v1.

### Linger

The hub runs as a **user** quadlet (`WantedBy=default.target`). Without
`loginctl enable-linger $USER` the user systemd instance is torn down when you
log out, and the hub stops. This is the single most common way a hub "works on
my machine" and is dead by morning.

### Rotation

Enrollment tokens are **one-time** — the hub consumes one on a successful
`/enroll`. Heartbeat tokens are **per-runner and revocable**. To rotate the
GitHub PAT, replace the value in `github-token.env` and restart the unit. Treat
the PAT as fleet-wide read access: it is the highest-value secret here, which
is why the hub is monitor-only (see Q3 below).

## Deployment steps (run these ON the hub machine)

### 1. Build the image and pin the base digest

```bash
cd /path/to/DevGate-Agentic-Framework
podman build -t devgate-hub:local -f templates/runner-monitor/Containerfile .
```

The `Containerfile` uses `FROM python:3.12-slim`. House standard is to **pin a
digest once you have validated a tag** — replace the tag with
`python:3.12-slim@sha256:<digest>` after you have built and run it once. There
are no `pip install` steps; the hub is stdlib-only, which keeps the image small
and the supply chain short.

### 2. Create the persistent volume

```bash
podman volume create devgate-hub-data
```

The quadlet's `Volume=devgate-hub-data:/data` mounts it. `runners.json` and
`alerts/` are created on first start. If you lose this volume you lose the
registry — recovery is re-enrolling every spoke, which is cheap but manual.

### 3. Mint the GitHub PAT and write the secrets drop-in

Create a **fine-grained** personal access token with, per watched repo:

- **Actions: read** — runner status, queued runs, check-runs, workflow runs
- **Issues: write** — file and comment on alert issues

Write it to a drop-in and lock the file down:

```bash
mkdir -p ~/.config/containers/systemd/devgate-hub.container.d
cat > ~/.config/containers/systemd/devgate-hub.container.d/secrets.env <<'EOF'
GITHUB_TOKEN=<your-fine-grained-PAT>
HUB_ENROLLMENT_TOKENS=<tok1>,<tok2>
EOF
chmod 600 ~/.config/containers/systemd/devgate-hub.container.d/secrets.env
```

`HUB_ENROLLMENT_TOKENS` is a comma-separated list; mint one per spoke you intend
to enroll so each can be consumed independently and revoked by removal.

Without `GITHUB_TOKEN` the hub still serves heartbeats but every API check is
skipped — it logs loudly rather than passing silently.

### 4. Choose the port and firewall it

The default is **8443**. Publish it in the quadlet (`PublishPort=8443:8443` is
already set) and open the host firewall to enrolled runner hosts only. If you
change the port, change it in **both** the quadlet and every spoke's hub URL.

### 5. Enable linger

```bash
loginctl enable-linger "$USER"
```

### 6. Install the quadlet and start it

```bash
cp templates/runner-monitor/devgate-hub.container \
   ~/.config/containers/systemd/devgate-hub.container
systemctl --user daemon-reload
systemctl --user start devgate-hub
systemctl --user status devgate-hub
podman logs devgate-hub
```

`LogDriver=k8s-file` is deliberate: rootless user journald is often absent on
hub hosts, which would leave service failures invisible.

### 7. Verify `/health`

```bash
curl -s http://127.0.0.1:8443/health
```

Expect:

```json
{"ok": true, "last_poll_at": "…", "last_alert_at": null,
 "registered_runners": 0, "uptime_sec": 12.3}
```

`last_poll_at` advancing is proof the API channel is live. `last_alert_at` is
`null` until the first alert — that is healthy, not broken.

### 8. Enable the dead-man switch

`.github/workflows/devgate-monitor-deadman.yml` is the monitor's monitor
(`mon-hub-01`, D6). See **Dead-man switch** below for what the committed
template does and does not catch before you rely on it.

## Enrolling a runner (run this ON the spoke)

```bash
scripts/runner-enroll.sh <hub-url> <enrollment-token> \
    --repo OWNER/REPO [--labels devgate] [--host-alias HOST] [--interval 300]
```

The script:

1. `POST /enroll` with the runner's identity and the one-time token.
2. On `200`, captures the per-runner `heartbeat_token` from the response.
3. Writes `$HOME/.devgate-heartbeat.env` **`chmod 600`** containing `HUB_URL`,
   `RUNNER_NAME`, `HEARTBEAT_TOKEN`, `LAST_JOB_SEEN`.
4. Installs `devgate-heartbeat.service` (one-shot: reads `df` and `podman info`,
   posts to `/heartbeat`) and `devgate-heartbeat.timer` under
   `~/.config/systemd/user/`, then enables and starts the timer.

Re-running enroll for an identity that is already registered is a no-op on the
hub side; the script keeps the existing heartbeat token path and re-installs the
timer. Enabling an already-enabled timer is harmless.

**Revoking** (spoke being retired, or a token you believe is compromised):

```bash
scripts/runner-enroll.sh --revoke <hub-url> <heartbeat-token> <runner-name>
```

This posts `/revoke`, which deletes the heartbeat token and marks the runner
`enrolled: false`; subsequent heartbeats get `401`. It then stops and removes
the local timer and the token file.

## Dead-man switch — read this before trusting it

The committed workflow (`devgate-monitor-deadman.yml`) runs every 6 hours on
GitHub's schedule and **prints a proof-of-life line**. Its own header states the
intent: the switch fires on *absence*, not on failure.

Watch the gap: a GitHub-scheduled workflow cannot natively notify you that it
*didn't* run, and the committed template does not call the hub. As shipped it is
a heartbeat record and a manual `workflow_dispatch` probe — it will **not**
page you if the hub container dies. To make it a real dead-man switch, add a
step that fetches the hub's `/health` and fails when `last_poll_at` is older
than a few poll intervals (or point an external monitor at `/health` and alert
on staleness). Do this before you rely on it, and record which of the two you
chose. Until then, the hub's own alerting is your only automatic signal, and a
dead hub is silent.

## Q1–Q3 — defaults, confirm before go-live

These are **config defaults in `hub/config.py`**, surfaced here for the owner to
confirm or override. They are deliberately not hardcoded into behavior.

| # | Question | Default | Override | Confirm |
| --- | --- | --- | --- | --- |
| Q1 | Alert channel | `github_issue` (`HUB_ALERT_CHANNEL`) | `null` = log-only | Is GitHub issues acceptable, or do you also need email/webhook? Email and webhook are **not wired in v1** — only the notifier interface exists. |
| Q2 | Heartbeat interval | 300 s / 5 min (`HUB_HEARTBEAT_INTERVAL_SEC`) | env, or `--interval` at enroll | Alerts fire after ~2 intervals (~10 min). Acceptable lag? |
| Q3 | Hub role | monitor-only (`HUB_MONITOR_ONLY=true`) | env | The hub does **not** register as a job runner. Keeping it monitor-only bounds the blast radius of the fleet-wide PAT. Opt in only deliberately. |

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `/health` unreachable from a spoke | host firewall rule missing, or the port differs between quadlet and spoke URL |
| `401 unknown_or_revoked_token` on enroll | token already consumed (they are one-time) or not in `HUB_ENROLLMENT_TOKENS` |
| `409 already_enrolled` | that `runner_name` is already registered; use `--revoke` first to re-enroll cleanly |
| No alerts ever, `last_poll_at` stale | `GITHUB_TOKEN` missing/expired, or PAT lacks `actions:read` |
| Alerts never appear as issues | PAT lacks `issues:write`, or the `devgate-monitor` label could not be created |
| Hub stops after logout | linger not enabled (`loginctl enable-linger $USER`) |

## Related

- [`templates/runner/README.md`](../templates/runner/README.md) — the
  self-hosted runner standard the spokes follow.
- [`templates/runner-monitor/Containerfile`](../templates/runner-monitor/Containerfile)
  and `devgate-hub.container` — the image and quadlet this runbook deploys.
- [`docs/RELEASE_GATE.md`](RELEASE_GATE.md) — the release gate suite.