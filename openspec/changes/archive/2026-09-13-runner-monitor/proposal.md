# Proposal: monitor-hub runner monitor — one hub that watches every DevGate runner

**Change ID:** 2026-09-13-monitor-hub-runner-monitor
**Source:** Owner request (Roger, 2026-09-13); motivating incident: the
`example-runner` runner stalled its queue and multiple commits shipped with no gate
results, discovered only by manual audit (2026-09-12 RADICAL QA).
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
home" to: registration at enrollment time, periodic heartbeats, and health
reporting. The hub independently polls the GitHub API (runner status, queued
workflow runs, check-run conclusions, scheduled-scan presence) so monitoring
works even before a spoke enrolls, and raises alerts when a runner goes
offline, a queue stops draining, gates go red, or drift scans go overdue.

## Non-goals

- Auto-remediation (restart runner containers, re-drain queues) — v1 alerts,
  a human acts.
- Replacing GitHub Actions' own runner management or job execution.
- Monitoring anything other than DevGate-standard runners and their gate
  evidence.
- Moving game development or any gate out of this repo (owner decision
  2026-09-13: one DevGate, not two).

## Success criteria

- Every runner deployed from `templates/runner/` can enroll with one command
  on its host and begins heartbeating within one interval.
- A runner that goes offline or stops draining its queue produces an alert
  within two heartbeat intervals (the `example-runner` failure class).
- A red gate run on any watched default branch produces an alert naming the
  repo, gate, and commit.
- A drift scan that is overdue by more than one scheduled period, or fails,
  produces an alert.
- No secrets, tokens, host IPs, or credentials are committed to this public
  repo — all instance state lives on monitor-hub.
