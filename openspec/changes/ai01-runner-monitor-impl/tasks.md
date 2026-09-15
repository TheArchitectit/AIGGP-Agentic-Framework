# Tasks: ai01-runner-monitor implementation (dependency-ordered)

Implements the archived change `2026-09-13-ai01-runner-monitor` (design D1–D7,
Sprints 1–6). No spec deltas expected — the requirements are already live in
`openspec/specs/{hub-architecture,runner-monitoring,enrollment-and-alerting}/`.

## Sprint 1 — hub skeleton (D1, D3)
- [x] 1.1 `hub/` Python service: /enroll, /heartbeat, /health endpoints +
      runners.json load/save on the hub volume (commit 2; schema/config/tokens
      in commit 1)
- [x] 1.2 runners.json JSON schema + redacted example committed (D3)
- [x] 1.3 Hub Containerfile + Podman quadlet template under
      templates/runner-monitor/ (commit 6)

## Sprint 2 — enrollment and heartbeat (D4, D2b)
- [x] 2.1 scripts/runner-enroll.sh: enroll, write devgate-heartbeat.timer,
      --revoke (commit 5)
- [x] 2.2 Hub: enrollment-token verification, per-runner heartbeat token
      issuance, stale-heartbeat detection (commits 1–2)
- [x] 2.3 Tests: enroll → heartbeat → stale cycle against a fixture hub (D2b)

## Sprint 3 — GitHub polling (D2a, D5)
- [x] 3.1 Poll runner status + queued-run age per registered repo (commit 3)
- [x] 3.2 Poll check-run conclusions on watched branches (commit 3)
- [x] 3.3 Poll scheduled drift-scan presence/recency (commit 3)

## Sprint 4 — alerting (D6)
- [x] 4.1 Alert engine: dedupe by (repo, check-class, runner), JSONL alert log
      (commit 4)
- [x] 4.2 GitHub-issue notifier with devgate-monitor label + notifier interface
      stub (commit 4)
- [x] 4.3 Dead-man switch workflow template for this repo (commit 7)

## Sprint 5 — monitor-hub deployment runbook (D7)
- [x] 5.1 docs/runner-monitor-monitor-hub.md: volume, token drop-in, enrollment
      tokens, port/firewall, linger, rotation (commit 7). Named for the spec's
      mon-monitor-hub-01 requirement (the plan's `runner-monitor-ai01.md` was
      superseded); quadlet + config.py pointers updated to match.
- [x] 5.2 secrets-hygiene check: no tokens/IPs/hosts in committed files (commit 7)

## Sprint 6 — closeout
- [x] 6.1 Suite green (pytest + new hub tests; pre-existing node failures noted,
      not claimed); README pointer from templates/runner/README.md; CHANGELOG;
      version bump per release gate (commit 7)
