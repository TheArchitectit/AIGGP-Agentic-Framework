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

## Executor notes

- Owner questions before Sprint 4 hardens defaults: Q1 alert channel
  (GitHub issues assumed), Q2 heartbeat interval (5 min assumed), Q3 hub
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
