# Design: monitor-hub runner monitor (hub-and-spoke, all-local)

## Locked decisions

D1. **Hub-and-spoke on monitor-hub, local-only.** One monitor hub runs on the monitor-hub
    machine as a container under the existing runner standard
    (ghcr.io/actions-runner base is NOT required — the hub is a small
    Python service; it ships its own thin image and Podman quadlet
    template alongside `templates/runner/`). Every project runner (spoke)
    talks home to it directly over the local network. monitor-hub is the single
    well-known hub because it already hosts the runner fleet. The hub
    binds to a loopback or LAN address only; nothing in this design is
    internet-facing.

D2. **Two independent evidence channels.**
    a) Hub-side polling: the hub calls the GitHub REST API for each
       registered repo/runner — runner online status, queued workflow runs
       and their age, check-run conclusions on watched branches, and the
       presence of scheduled drift-scan runs. This works from day one,
       even for runners not yet enrolled. All polling is OUTBOUND-ONLY:
       the hub initiates every connection to api.github.com and nothing
       connects back in.
    b) Spoke heartbeats: each enrolled runner posts a heartbeat
       (runner name, labels, last job seen, local disk/podman health) on a
       systemd timer, directly to the hub over the local network (same
       host or LAN). This catches host-level failure the API cannot see —
       a dead quadlet still shows "offline" in the API eventually, but the
       heartbeat explains *why* and fails faster.

D3. **Registry: schema in-repo, instance data on monitor-hub.** `runners.json`
    (schema documented here) maps runner name → repo, labels, enrolled-at,
    last heartbeat, alert state. The file lives on the hub's persistent
    volume on monitor-hub and is NEVER committed: this repo is public and the
    registry is instance state. Only the JSON schema and an example with
    placeholder values ship in-repo.

D4. **Enrollment flow (talk home, local network only).** After the
    standard quadlet setup, the operator runs
    `scripts/runner-enroll.sh <hub-url> <enrollment-token>` on the runner
    host, where `<hub-url>` is the hub's local-network address (loopback
    or LAN, e.g. `http://monitor-hub.internal:<port>`). The script POSTs the runner's
    identity (name, repo, labels, host alias) to the hub's `/enroll`
    endpoint over the local network; the hub verifies the one-time
    enrollment token (minted by the owner, held in the hub's env drop-in),
    records the runner, and returns a per-runner heartbeat token. The
    script writes a systemd user timer (`devgate-heartbeat.timer`) that
    POSTs the heartbeat to the same local address. Unenrolling is
    `runner-enroll.sh --revoke`, which deletes the heartbeat token.

D5. **What the monitor checks.**
    - **Runner online:** GitHub API runner status is `online` AND heartbeat
      is fresh (missed two intervals → stale). Either failing raises.
    - **Queue drain:** any queued workflow run older than a threshold
      (default 30 min, per-repo override) targeting a registered label.
      This is the `example-runner` failure class, caught in minutes instead
      of days.
    - **Gate results:** latest check-run conclusions per watched branch
      (default branch at minimum). A `failure`/`timed_out` conclusion
      raises an alert naming repo, gate, commit SHA.
    - **Drift:** each repo's scheduled drift-scan must have a completed run
      within one scheduled period + grace; an overdue or failed scan raises.

D6. **Failure alerting (local or outbound-only).** Default channel: a
    GitHub issue filed (or an existing open alert issue updated) on the
    affected repo by the hub's token, tagged `devgate-monitor` — an
    OUTBOUND-ONLY API write from the hub, so it needs no inbound path —
    plus an append-only JSONL alert log on the hub volume (purely local).
    Alerts dedupe: one open issue per (repo, check-class, runner); the
    hub comments on recurrence instead of spamming new issues. Additional
    notifiers (email, webhook) are behind a notifier interface, out of
    scope for v1 beyond the interface; any future notifier must also be
    local or outbound-only.

D7. **In-repo vs on-monitor-hub split.**
    - In this repo: hub service source, its Containerfile + quadlet
      template, `runner-enroll.sh`, heartbeat timer unit templates,
      runners.json schema + redacted example, tests, and docs.
    - On the monitor-hub machine (documented runbook, not committed): create the
      hub's persistent volume, mint the GitHub API token (fine-grained,
      `actions:read` + `issues:write` per watched repo) into an env
      drop-in (`chmod 600`, never committed), mint enrollment tokens,
      bind the hub listen address (loopback or LAN only), enable linger,
      and start the quadlet. No inbound firewall rule into the owner's
      environment is opened at any step.

D8. **Network posture: all local, outbound-only externally (owner
    steering, 2026-09-13).** Per Roger: "all local, all runners talk
    directly to the runner for the gate. we aren't opening up firewall
    rules inbound to my env". Consequences applied across this package:
    - Spoke → hub enrollment and heartbeats travel only over the local
      network (same host or LAN); the hub is the only endpoint spokes
      know, and it is a local address.
    - The hub exposes NO internet-facing listener and requires NO inbound
      firewall rule into the owner's environment.
    - Every external interaction (GitHub API polling, alert-issue filing,
      hub status publication for the dead-man switch) is an outbound
      connection the hub initiates.
    - The dead-man switch therefore CANNOT probe the hub from the internet
      (see risk table): the hub publishes its own freshness status
      outbound, and a scheduled workflow reads that published state back
      through the GitHub API.

## Open questions

Q1. Alert channel confirmation: GitHub issues on the affected repo stays
    the default because filing them is an outbound-only API write from
    the hub, which fits the all-local posture — acceptable to the owner,
    or should alerts stay purely local (JSONL log + on-host notification
    only)? Awaiting Roger's call.
Q2. Heartbeat interval default: 5 min proposed (alerts within ~10 min of
    a stall). Local-network volume is trivial either way.
Q3. Does the hub container also register as a DevGate *job* runner (i.e.
    run gate jobs itself), or is it monitor-only? Proposal: monitor-only —
    a runner that executes project jobs AND holds the fleet API token
    widens the token's blast radius.

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Hub token leaks fleet-wide read access | Medium | Fine-grained PAT, minimum scopes, env drop-in on monitor-hub only, rotation note in runbook |
| Hub itself dies silently | Medium | Outbound-published dead-man switch: the hub posts its last-poll/last-alert timestamp to a pinned `devgate-monitor-status` issue in this repo (outbound API write); a GitHub-scheduled workflow reads that issue via the API and alerts when the timestamp is stale. No inbound probe of the hub exists |
| Heartbeat spoofing / stray posts | Low | Per-runner heartbeat tokens issued at enrollment; hub rejects unknown tokens; hub binds to a local address so the listener is never internet-reachable |
| API rate limits with many repos | Low | Poll cycle is per-repo sequential with backoff; runner counts here are small |
| Registry loss on monitor-hub disk failure | Low | Registry is rebuildable by re-enrolling runners; volume is on the same host as the runners it watches, and the JSONL alert log is append-only |
