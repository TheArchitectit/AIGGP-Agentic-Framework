# Runbook: Hub Outage

**Scope:** the runner-monitor hub is unreachable or wedged. This runbook
covers the implemented detection and recovery path only.

## What you will see

- Each spoke runs `scripts/hub-watchdog.sh` on a timer
  (`devgate-hb-watchdog-<runner>.timer`). When the hub is down, the
  watchdog exits 1 with `HUB UNREACHABLE` — **the failed systemd unit on
  the spoke is the signal** (local-only by design; no GitHub issue is
  filed from spokes).
- `python3 scripts/fleet_drill.py` step `watchdog-dead-hub-exit-1`
  demonstrates this exact path.

## Diagnosis

```bash
# From any spoke:
systemctl --user status devgate-hb-watchdog-<runner>.service
HUB_URL=https://<hub>:8443 bash scripts/hub-watchdog.sh

# From the hub host:
systemctl status devgate-hub        # or: podman logs devgate-hub
curl -fsS http://127.0.0.1:8443/health
```

`/health` fields that matter (see `hub/server.py`):
- `ok: true` + `polling_enabled: false` → hub alive, API polling off by
  configuration (not an outage). The watchdog reports `warn
  polling_disabled`, exit 0.
- `ok: true` + `polling_enabled: true` + stale `last_poll_at` → poll loop
  wedged; the watchdog fails it once the grace window passes
  (`max(poll_interval*5, 300)s`).
- connection refused / timeout → process or host down.

## Recovery

1. Restart the hub service. The fleet registry (`runners.json`) lives on
   the hub volume and survives restarts — verified by
   `scripts/fleet_drill.py` (`heartbeat-after-restart-ok`,
   `registry-count-survives-restart`). Enrollment tokens do NOT need to be
   reissued; per-runner heartbeat tokens keep working.
2. Confirm recovery from a spoke: the watchdog returns to exit 0
   (`ok last_poll_Ns_ago` or `warn polling_disabled`), and a manual
   heartbeat succeeds:

```bash
curl -fsS -X POST -H 'Content-Type: application/json' \
  -d "{\"runner_name\":\"<name>\",\"heartbeat_token\":\"<token>\"}" \
  https://<hub>:8443/heartbeat
```

## What NOT to do

- Do not re-enroll runners to "fix" a hub outage. Enrollment consumes
  one-time tokens and creates duplicate runner entries (the hub answers
  409 for an already-enrolled name).
- Do not disable the watchdog timer to silence the failure — it is the
  only channel that notices hub death when GitHub-side polling is also down.
