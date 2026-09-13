# Handoff: monitor-hub-runner-monitor

## Traceability

| Motivation | Spec requirement | Sprint |
|---|---|---|
| example-runner stalled queue, 8 unverified commits | mon-queue-01 | 3 |
| Runner offline invisible until audit | mon-online-01, mon-channels-01 | 2, 3 |
| No aggregated gate results | mon-gates-01 | 3 |
| Drift scans rot silently | mon-drift-01 | 3 |
| Hand-rolled enrollment | mon-enroll-01, mon-hub-01 | 1, 2 |
| Alert routing + no committed secrets | mon-alert-01, mon-registry-01, mon-monitor-hub-01 | 4, 5 |
| Owner steering 2026-09-13: all local, no inbound firewall openings | mon-local-01, mon-hub-01, mon-enroll-01, mon-alert-01, mon-monitor-hub-01 | 1, 2, 4, 5 |

## Executor notes

- Owner steering applied 2026-09-13 (verbatim): "all local, all runners
  talk directly to the runner for the gate. we aren't opening up firewall
  rules inbound to my env". Design D8 locks the posture: spoke→hub traffic
  is local-network only, the hub exposes no internet-facing listener, and
  every external call (polling, alert issues, status publication) is
  outbound from the hub. Do not reintroduce any inbound path.
- The dead-man switch is outbound-published: the hub posts its freshness
  timestamp to a pinned `devgate-monitor-status` issue and the scheduled
  workflow reads it back through the GitHub API. A workflow probing the
  hub directly would violate the no-inbound rule — do not build that.
- Owner questions before Sprint 4 hardens defaults: Q1 alert channel
  (GitHub issues assumed — kept because they are outbound-only; a purely
  local option is offered), Q2 heartbeat interval (5 min assumed), Q3 hub
  is monitor-only (assumed) — all go back to Roger with this package; do
  not guess.
- Secrets hygiene is load-bearing: this repo is public. tokens, host IPs,
  and live registry data live only on monitor-hub (mon-registry-01, mon-monitor-hub-01).
- The hub is a small Python service, NOT a second actions-runner container
  (design D1); it ships its own thin image + quadlet template.
- Heartbeat tokens are per-runner and revocable; enrollment tokens are
  one-time. Both are minted on monitor-hub per the runbook, never committed.
- This package does not touch game-dev gates or specs — per the owner's
  2026-09-13 decision, game dev stays in this repo (one DevGate).
