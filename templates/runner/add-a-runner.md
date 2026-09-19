# Adding a Runner to an Existing Fleet

Use this when you already have runners on a host (a shared `dg-entrypoint.sh`,
a monitor-hub, existing quadlets) and you need to add the N+1th.

Do NOT fork the entrypoint — all runners on a host share one bind-mounted
`dg-entrypoint.sh`. Duplicating it creates a parallel maintenance surface.

## 1. Quadlet

Copy the base pattern from an existing runner quadlet on the host. Change:

| Field | Value |
|---|---|
| `ContainerName` | `devgate-runner-<project>` |
| `HostName` | `devgate-runner-<project>` |
| `RUNNER_NAME` | `<host>-<project>` |
| `RUNNER_LABELS` | `devgate` (plus extras if needed) |
| `REPO_URL` | `https://github.com/OWNER/REPO` |
| `Volume` | `devgate-runner-<project>-work:/_work` |
| `Mount` (entrypoint) | bind-mount the **shared** entrypoint, not a fork |

Place at `~/.config/containers/systemd/devgate-runner-<project>.container`.

### Image

The stock pinned image (`ghcr.io/actions/actions-runner@sha256:…`, Ubuntu 24.04,
passwordless sudo, node20/py3.12/git) is sufficient unless your gates need a
compiler or runtime not already in the base. Check whether the repo's CI
installs extra packages per run (`apt-get`, `pip install`, `go install`):
those are candidates for a custom Containerfile if they dominate run time.
Otherwise, stay on stock.

## 2. Token

Mint a one-time registration token:

```bash
gh api -X POST \
  repos/OWNER/REPO/actions/runners/registration-token \
  --jq .token | \
  { printf "RUNNER_TOKEN="; cat; printf "\n"; } \
  > ~/.config/containers/systemd/devgate-runner-<project>.secrets.env
chmod 600 ~/.config/containers/systemd/devgate-runner-<project>.secrets.env
```

The token is piped raw — it never enters argv, shell history, or stdout. Verify
the shape (`^[A-Za-z0-9_-]{20,}$`) and permissions (`600`) before daemon-reload.

The shipped quadlet declares
`EnvironmentFile=-%h/.config/containers/systemd/<project>-runner.secrets.env`
(see [`self-hosted-runner.container`](self-hosted-runner.container)); match
that filename when you rename the project. That file is a RAW env file read by
the unit — not a quadlet drop-in: `.container.d/*.conf` fragments are merged as
quadlet INI and expect `[Container]` / `Environment=` lines, so a bare
`RUNNER_TOKEN=` file placed there does not parse (the mechanism this walkthrough
used to describe). The leading `-` makes the file optional at unit-parse time;
the token stays in place for the lifetime of the runner, but durability comes
from the entrypoint's credential pre-seed, not from the token surviving a
restart.

## 3. Submodule transport

If the repo uses a `.devgate` submodule (or any other submodule), the URL in
`.gitmodules` must be reachable from inside the runner container:

- **Public submodule** → use HTTPS. Zero credential needed, no key mount.
  Example: `url = https://github.com/OWNER/REPO.git`
- **Private submodule** → use SSH with a per-repo deploy key. Create a
  read-only deploy key on the submodule repo, mount it into the container at
  `~/.ssh/id_ed25519` (or equivalent), and use the SSH URL in `.gitmodules`.

Inside the container, the host's default SSH key authenticates as ONE GitHub
identity — whatever the key was registered as. If the submodule repo is
different from the runner's repo, the SSH URL resolves the wrong identity and
the checkout fails. HTTPS avoids this entirely for public repos.

## 4. Start and verify

```bash
systemctl --user daemon-reload
systemctl --user start devgate-runner-<project>
systemctl --user status devgate-runner-<project>
```

Then:

```bash
# Runner should appear online
gh api repos/OWNER/REPO/actions/runners --jq '.runners[] | {name,status}'

# Logs should show "Listening for Jobs"
podman logs devgate-runner-<project>
```

## 5. Durability

On restart the shared entrypoint pre-seeds `/.runner`, `.credentials`, and
`.credentials_rsaparams` from the persistent work volume (`CFGDIR`). If these
exist, `config.sh` is skipped and the existing registration is reused. The
token env file is still needed at unit-parse time (see above) but its value
is not re-read after the first registration.

Test with a graceful restart:

```bash
systemctl --user restart devgate-runner-<project>
# Runner should come back with the same runnerId
gh api repos/OWNER/REPO/actions/runners --jq '.runners[] | {name,id}'
```

## 6. Monitor enrollment (optional)

If the fleet has a monitor-hub:

```bash
scripts/runner-enroll.sh <hub-url> <enrollment-token> --repo OWNER/REPO
```

See `docs/runner-monitor-monitor-hub.md` for hub setup; the enrollment script
installs a heartbeat timer and a hub watchdog.

## 7. Private infra record

Machine-specific details — hostname, IP, volume layout, incident log — belong
in the operator's private infra repo. The public DevGate repo stays generic
by design. Add a section to the private fleet doc mirroring the existing
entries: runner name, repo, labels, quadlet path, image decision, and the
first-run verdict.

---

*See `templates/runner/README.md` for first-provision (no existing fleet),
and `.gitignore` for the private-repo pointer.*