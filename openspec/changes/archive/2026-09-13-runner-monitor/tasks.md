# Tasks: monitor-hub runner monitor (dependency-ordered)

## Sprint 1 — hub skeleton (D1, D3, D8)
- [ ] 1.1 hub/ Python service: /enroll, /heartbeat, /health endpoints +
      runners.json load/save on the hub volume; bind address configurable,
      loopback or LAN only, never an internet-facing interface (D1, D3, D8)
- [ ] 1.2 runners.json JSON schema + redacted example committed (D3)
- [ ] 1.3 Hub Containerfile + Podman quadlet template under
      templates/runner-monitor/ (D1)

## Sprint 2 — enrollment and heartbeat (D4, D2b)
- [ ] 2.1 scripts/runner-enroll.sh: enroll against the hub's local-network
      address, write devgate-heartbeat.timer, --revoke (D4)
- [ ] 2.2 Hub: enrollment-token verification, per-runner heartbeat token
      issuance, stale-heartbeat detection (D4, D5)
- [ ] 2.3 Tests: enroll → heartbeat → stale cycle against a fixture hub on
      loopback (D2b)

## Sprint 3 — GitHub polling, outbound-only (D2a, D5, D8)
- [ ] 3.1 Poll runner status + queued-run age per registered repo (D5:
      runner online, queue drain)
- [ ] 3.2 Poll check-run conclusions on watched branches (D5: gate results)
- [ ] 3.3 Poll scheduled drift-scan presence/recency (D5: drift)

## Sprint 4 — alerting, local or outbound-only (D6, D8)
- [ ] 4.1 Alert engine: dedupe by (repo, check-class, runner), JSONL alert
      log on hub volume
- [ ] 4.2 GitHub-issue notifier with `devgate-monitor` label (outbound API
      writes only) + notifier interface stub
- [ ] 4.3 Dead-man switch: hub publishes its last-poll/last-alert timestamp
      outbound to a pinned `devgate-monitor-status` issue; scheduled
      workflow template for this repo reads it back via the API and alerts
      on staleness — no inbound probe of the hub (D8, risk table)

## Sprint 5 — monitor-hub deployment runbook (D7, D8)
- [ ] 5.1 docs/runner-monitor-monitor-hub.md: volume, token drop-in, enrollment
      tokens, local listen-address binding (loopback or LAN only, no
      inbound firewall openings), linger, rotation (D7, D8)
- [ ] 5.2 secrets-hygiene check: no tokens/IPs/hosts in committed files

## Sprint 6 — closeout
- [ ] 6.1 Suite green; README pointer from templates/runner/README.md;
      CHANGELOG; version bump per release gate
