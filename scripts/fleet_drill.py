#!/usr/bin/env python3
"""fleet_drill.py — an end-to-end drill of the runner-monitor fleet path.

Exercises the least-observed code in the repo through REAL processes and
REAL HTTP: the actual hub subprocess (`python3 -m hub.main`), the actual
wire protocol the spokes speak (enroll/heartbeat/revoke/health), the actual
watchdog script (`scripts/hub-watchdog.sh`), and hub RESTART with registry
persistence. One-time-token consumption, duplicate-enroll rejection,
revocation semantics, and post-restart token survival are all asserted
against observed HTTP behavior, never mocks.

This is a DRILL, not a week of production soak: --hold-seconds extends the
heartbeat soak (default 10s). Polling against the GitHub API is NOT part of
this drill (it needs a real token and fleet) — the watchdog's
polling_disabled warn path IS.

Exit codes: 0 all steps held; 1 any step failed; 30 usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

DEVGATE_ROOT = Path(__file__).resolve().parent.parent
WATCHDOG = DEVGATE_ROOT / "scripts" / "hub-watchdog.sh"

EXIT_OK = 0
EXIT_DRILL_FAILED = 1
EXIT_USAGE = 30

_results = []


def step(name: str, ok: bool, detail: str = "") -> bool:
    _results.append((name, ok))
    mark = "PASS" if ok else "FAIL"
    print(f"  {mark}  {name:34s} {detail}")
    return ok


def http(method: str, url: str, payload: dict = None, timeout: float = 10):
    """Returns (status_code, parsed_json_or_None). Connection errors raise."""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, None


class Hub:
    """The real hub as a subprocess, on a real socket."""

    def __init__(self, data_dir: Path, port: int, tokens: list):
        env = dict(os.environ)
        env["HUB_ENROLLMENT_TOKENS"] = ",".join(tokens)
        env.pop("GITHUB_TOKEN", None)  # drill runs without API polling
        self.port = port
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "hub.main",
             "--bind-host", "127.0.0.1", "--bind-port", str(port),
             "--data-dir", str(data_dir)],
            cwd=str(DEVGATE_ROOT), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def wait_healthy(self, timeout: float = 15.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                return False
            try:
                code, body = http("GET", self.url("/health"), timeout=2)
                if code == 200 and body and body.get("ok"):
                    return True
            except OSError:
                pass
            time.sleep(0.2)
        return False

    def stop(self, sig=signal.SIGTERM) -> int:
        self.proc.send_signal(sig)
        return self.proc.wait(timeout=15)


def main() -> int:
    ap = argparse.ArgumentParser(prog="fleet_drill",
                                 description="end-to-end fleet-path drill")
    ap.add_argument("--hold-seconds", type=int, default=10,
                    help="heartbeat soak duration after enrollment")
    args = ap.parse_args()

    port = 18300 + (os.getpid() % 1000)  # reproducible-ish, collision-tolerant
    tokens = [f"drill-one-time-{port}-a", f"drill-one-time-{port}-b"]

    with tempfile.TemporaryDirectory(prefix="fleet-drill-") as td:
        data_dir = Path(td) / "data"
        data_dir.mkdir()
        print(f"fleet drill: hub on 127.0.0.1:{port}, data {data_dir}")

        # 1. LAUNCH + health
        hub = Hub(data_dir, port, tokens)
        if not step("hub-launch-and-health",
                    hub.wait_healthy()):
            hub.stop()
            return EXIT_DRILL_FAILED

        # 2-6. Enrollment semantics
        code, body = http("POST", hub.url("/enroll"), {
            "runner_name": "drill-runner-1", "repo": "example/repo",
            "enrollment_token": tokens[0], "labels": ["drill"],
            "host_alias": "drill-host"})
        step("enroll-ok", code == 200 and bool(body.get("heartbeat_token")),
             f"exit {code}")
        hb1 = (body or {}).get("heartbeat_token", "")

        code, _ = http("POST", hub.url("/enroll"), {
            "runner_name": "drill-runner-1", "repo": "example/repo",
            "enrollment_token": tokens[1]})
        step("enroll-duplicate-rejected-409", code == 409, f"exit {code}")

        code, _ = http("POST", hub.url("/enroll"), {
            "runner_name": "drill-runner-2",
            "repo": "example/repo", "enrollment_token": "wrong-token"})
        step("enroll-bad-token-rejected-401", code == 401, f"exit {code}")

        code, body2 = http("POST", hub.url("/enroll"), {
            "runner_name": "drill-runner-2", "repo": "example/repo",
            "enrollment_token": tokens[1]})
        hb2 = (body2 or {}).get("heartbeat_token", "")
        step("enroll-second-runner-ok", code == 200 and bool(hb2),
             f"exit {code}")

        code, _ = http("POST", hub.url("/enroll"), {
            "runner_name": "drill-runner-3", "repo": "example/repo",
            "enrollment_token": tokens[0]})
        step("enroll-one-time-token-not-reusable-401", code == 401,
             f"exit {code}")

        # 7-8. Heartbeat semantics
        code, _ = http("POST", hub.url("/heartbeat"), {
            "runner_name": "drill-runner-1", "heartbeat_token": hb1,
            "last_job_seen": None, "disk_ok": True, "podman_ok": True})
        step("heartbeat-ok", code == 200, f"exit {code}")

        code, _ = http("POST", hub.url("/heartbeat"), {
            "runner_name": "drill-runner-1",
            "heartbeat_token": "forged"})
        step("heartbeat-forged-token-401", code == 401, f"exit {code}")

        # 9. Health reflects the fleet
        code, health = http("GET", hub.url("/health"))
        step("health-counts-runners",
             code == 200 and health.get("registered_runners") == 2,
             f"runners={health.get('registered_runners')}")
        step("health-reports-polling-disabled-honestly",
             health.get("polling_enabled") is False)

        # 10. Watchdog against the ALIVE hub (real script, real HTTP)
        env = dict(os.environ, HUB_URL=hub.url(""))
        wd = subprocess.run(["bash", str(WATCHDOG)], capture_output=True,
                            text=True, env=env, timeout=60)
        step("watchdog-alive-hub-exit-0", wd.returncode == 0,
             (wd.stderr.strip().splitlines() or [""])[0][:60])

        # 11. RESTART: clean shutdown, then relaunch on the same volume
        rc = hub.stop(signal.SIGTERM)
        step("hub-clean-shutdown-exit-0", rc == 0, f"exit {rc}")
        hub = Hub(data_dir, port, tokens)  # same data dir; tokens irrelevant now
        step("hub-restart-with-persisted-registry",
             hub.wait_healthy())

        # 12. Tokens survive the restart
        code, _ = http("POST", hub.url("/heartbeat"), {
            "runner_name": "drill-runner-1", "heartbeat_token": hb1})
        step("heartbeat-after-restart-ok", code == 200, f"exit {code}")
        code, health = http("GET", hub.url("/health"))
        step("registry-count-survives-restart",
             health.get("registered_runners") == 2,
             f"runners={health.get('registered_runners')}")

        # 13. Revocation semantics
        code, _ = http("POST", hub.url("/revoke"), {
            "runner_name": "drill-runner-2", "heartbeat_token": hb2})
        step("revoke-ok", code == 200, f"exit {code}")
        code, _ = http("POST", hub.url("/heartbeat"), {
            "runner_name": "drill-runner-2", "heartbeat_token": hb2})
        step("heartbeat-after-revoke-401", code == 401, f"exit {code}")

        # 14. Soak: sustained heartbeats under the restarted hub
        failures = 0
        held = 0
        deadline = time.monotonic() + max(0, args.hold_seconds)
        while time.monotonic() < deadline:
            code, _ = http("POST", hub.url("/heartbeat"), {
                "runner_name": "drill-runner-1", "heartbeat_token": hb1})
            if code != 200:
                failures += 1
            held += 1
            time.sleep(1.0)
        step(f"soak-{held}-heartbeats-no-failures",
             held > 0 and failures == 0, f"failures={failures}")

        # 15. Watchdog against a DEAD hub
        hub.stop()
        wd = subprocess.run(["bash", str(WATCHDOG)], capture_output=True,
                            text=True, env=env, timeout=60)
        step("watchdog-dead-hub-exit-1", wd.returncode == 1,
             (wd.stderr.strip().splitlines() or [""])[0][:60])

    failed = [n for n, ok in _results if not ok]
    print(f"\nfleet drill: {len(_results) - len(failed)}/{len(_results)} "
          f"steps held")
    if failed:
        print("FAILED: " + ", ".join(failed))
        return EXIT_DRILL_FAILED
    print("fleet drill: PASS — enroll, heartbeat, revoke, watchdog, "
          "restart persistence, and soak all held")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
