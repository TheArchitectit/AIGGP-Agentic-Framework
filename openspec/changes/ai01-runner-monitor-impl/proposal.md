# Proposal: ai01-runner-monitor-impl

> Added 2026-09-19 (migrate-specs-to-openspec-conventions task 2.3): this
> change predates the repo's OpenSpec conventions and shipped with only a
> `plan.md`. The proposal below is derived from that plan and the landed
> implementation; it documents what was built and why. The implementation is
> complete except task 7.5 (live deploy verification on a real hub host,
> explicitly `NOT_RUN: needs the hub host`).

## Why

The self-hosted runner standard (templates/runner/) gave the fleet runners but
no way to see them: a stalled queue, an offline runner, a red gate, or a
missed drift scan was discoverable only by logging into each host. GitHub's
own runner list shows hosted and self-hosted runners but nothing about queue
age, watched-branch gate conclusions, or drift-scan recency — and nothing at
all detects the monitor's own absence. The archived design change
`2026-09-13-runner-monitor` (D1–D7) specified a hub-and-spoke monitor; this
change implements it.

## What Changes

- A stdlib-only Python hub (`hub/`): `/enroll` (one-time tokens), `/heartbeat`
  (per-runner revocable tokens), `/revoke`, `/health`; an atomic `runners.json`
  registry on the hub volume (never committed, schema + redacted example in
  `hub/schema/`).
- A GitHub API polling loop (`hub/monitor.py`) combining four check classes —
  runner online status, queue-drain age, check-run conclusions on watched
  branches, drift-scan recency — with spoke heartbeats as independent
  evidence channels (mon-channels-01).
- Deduplicated alerting (`hub/alerts.py`): one GitHub issue per
  (repo, check-class, runner), recurrence as comments under a cooldown, every
  event appended to a daily JSONL audit log.
- A spoke-side dead-man switch (`scripts/hub-watchdog.sh` +
  `scripts/runner-enroll.sh` installing systemd user timers): each spoke fails
  its own unit when the hub is unreachable or its poll loop wedges
  (mon-deadman-01) — the hub cannot report its own death.
- Deployment assets: `templates/runner-monitor/` (Containerfile + quadlet) and
  the runbook `docs/runner-monitor-monitor-hub.md`.
- Honest defaults: loopback bind, polling disabled (loudly) without
  `GITHUB_TOKEN`, monitor-only posture.

Locked decisions D1–D7 from the archived design are treated as fixed; Q1–Q3
land as config with defaults (`hub/config.py`), flagged for owner confirmation
in the runbook.

## Impact

- Affected specs: `hub-architecture`, `runner-monitoring`,
  `enrollment-and-alerting` (requirements `mon-*`; delivered deltas live in
  `openspec/changes/archive/2026-09-13-runner-monitor/specs/`).
- Affected code: `hub/`, `scripts/runner-enroll.sh`, `scripts/hub-watchdog.sh`,
  `templates/runner-monitor/`, `docs/runner-monitor-monitor-hub.md`; tests
  `tests/test_hub_*.py`.
