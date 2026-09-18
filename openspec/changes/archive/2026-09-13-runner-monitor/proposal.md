# Proposal: monitor-hub runner monitor — one hub that watches every DevGate runner

**Change ID:** 2026-09-13-monitor-hub-runner-monitor
**Source:** Owner request (Roger, 2026-09-13); motivating incident: the
`example-runner` runner stalled its queue and multiple commits shipped with no gate
results, discovered only by manual audit (2026-09-12 RADICAL QA).
Owner steering (2026-09-13): "all local, all runners talk directly to the
runner for the gate. we aren't opening up firewall rules inbound to my
env" — the design is fully local; nothing internet-facing.
**Status:** Proposed

## Problem

DevGate's self-hosted runner standard (`templates/runner/`) is being rolled
out per project: one ghcr.io/actions-runner container per repo, registered
with project-specific labels, deployed as Podman quadlets on the monitor-hub
machine. Each runner is an island:

1. **A stalled runner is invisible until someone audits.** The standard is
   deliberately fail-closed — jobs queue when no runner answers — but
   "queued forever" only gets noticed when a human looks. `example-runner`
   stopped draining its queue and multiple commits landed unverified by their own
   gates. Nothing paged anyone.
2. **Gate results are not aggregated.** Each repo's CI keeps its own
   check-run history; there is no one place that answers "is every gated
   main green right now?"
3. **Drift scans rot silently.** Scheduled drift scans are the early-warning
   arm of the framework; if a schedule stops firing or starts failing on one
   runner, no other system notices.
4. **Enrollment is hand-rolled each time.** Standing up a new runner means
   copying the quadlet, picking labels, and hoping the operator remembers to
   wire monitoring later.

## Scope

A monitor hub, itself deployed as a container on the monitor-hub machine under the
same runner standard, that every new and existing DevGate runner "talks
home" to DIRECTLY over the local network: registration at enrollment time,
periodic heartbeats, and health reporting. The hub independently polls the
GitHub API (runner status, queued workflow runs, check-run conclusions,
scheduled-scan presence) so monitoring works even before a spoke enrolls,
and raises alerts when a runner goes offline, a queue stops draining, gates
go red, or drift scans go overdue.

Network posture (owner steering 2026-09-13): everything is local or
outbound-only. Spoke-to-hub traffic stays on the local network (same host
or LAN); the hub binds to loopback or LAN addresses only and exposes no
internet-facing listener; no inbound firewall rule into the owner's
environment is opened; every external interaction (GitHub API polling,
alert-issue filing, hub status publication) is an outbound connection the
hub initiates.

## Non-goals

- Auto-remediation (restart runner containers, re-drain queues) — v1 alerts,
  a human acts.
- Replacing GitHub Actions' own runner management or job execution.
- Monitoring anything other than DevGate-standard runners and their gate
  evidence.
- Any internet-facing endpoint, inbound firewall opening into the owner's
  environment, or spoke/hub traffic routed over the internet (owner
  steering 2026-09-13).
- Moving game development or any gate out of this repo (owner decision
  2026-09-13: one DevGate, not two).

## Success criteria

- Every runner deployed from `templates/runner/` can enroll with one command
  on its host and begins heartbeating within one interval, talking directly
  to the monitor-hub hub over the local network.
- A runner that goes offline or stops draining its queue produces an alert
  within two heartbeat intervals (the `example-runner` failure class).
- A red gate run on any watched default branch produces an alert naming the
  repo, gate, and commit.
- A drift scan that is overdue by more than one scheduled period, or fails,
  produces an alert.
- Deployment requires no inbound firewall rule into the owner's environment
  and the hub exposes no internet-facing listener; all external calls are
  outbound from the hub.
- No secrets, tokens, host IPs, or credentials are committed to this public
  repo — all instance state lives on monitor-hub.
