"""Tests for hub/server.py (Sprint 2.3): enroll -> heartbeat -> stale cycle.

Spawns a fixture hub on an EPHEMERAL port (bind 0, read back) so tests never
collide with each other or with a real hub. Locks mon-enroll-01 (one-time
enrollment token, per-runner heartbeat token, revoke) and the /health
dead-man-switch endpoint shape.

Dual-runnable: pytest collects test_*; `python3 tests/test_hub_enroll_heartbeat.py` runs them too.
"""
import json
import sys
import threading
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.config import Config  # noqa: E402
from hub.server import create_server  # noqa: E402


class HubFixture:
    """A live hub subprocess-free fixture on an ephemeral port."""

    def __init__(self, tmp_path: Path, enrollment_token: str = "test-enroll-token-PLACEHOLDER"):
        config = Config()
        config.data_dir = str(tmp_path / "hubdata")
        self.config = config
        self.server = create_server(config, bind=("127.0.0.1", 0))
        self.port = self.server.server_address[1]
        self.state = self.server.hub_state  # type: ignore[attr-defined]
        self.state.registry.add_enrollment_token(enrollment_token)
        self.state.registry.save()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        while True:
            try:
                self.server.handle_request()
            except OSError:
                return

    def close(self):
        import socket
        # close the listening socket to unblock handle_request
        self.server.socket.close()
        self.server.server_close()

    def post(self, path: str, payload: dict) -> tuple[int, dict]:
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:  # noqa: PERF203
            return e.code, json.loads(e.read().decode())

    def get(self, path: str) -> tuple[int, dict]:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:  # noqa: PERF203
            return e.code, json.loads(e.read().decode())


def test_enroll_happy_path(tmp_path):
    hub = HubFixture(tmp_path)
    try:
        code, body = hub.post("/enroll", {
            "runner_name": "r1", "repo": "OWNER/REPO", "labels": ["devgate"],
            "host_alias": "monitor-hub", "enrollment_token": "test-enroll-token-PLACEHOLDER"})
        assert code == 200, body
        assert body["ok"] is True
        assert body["heartbeat_token"]
        # one-time token is consumed: replay fails with 401
        code2, body2 = hub.post("/enroll", {
            "runner_name": "r2", "repo": "OWNER/REPO",
            "enrollment_token": "test-enroll-token-PLACEHOLDER"})
        assert code2 == 401, body2
        assert body2["error"] == "unknown_or_revoked_token"
    finally:
        hub.close()


def test_enroll_bad_request_and_conflict(tmp_path):
    hub = HubFixture(tmp_path)
    try:
        # missing repo -> 400
        code, body = hub.post("/enroll", {"runner_name": "r1",
                                          "enrollment_token": "test-enroll-token-PLACEHOLDER"})
        assert code == 400 and body["error"] == "bad_request"
        # enroll r1, then re-enroll same name -> 409
        code, _ = hub.post("/enroll", {"runner_name": "r1", "repo": "OWNER/REPO",
                                       "enrollment_token": "test-enroll-token-PLACEHOLDER"})
        assert code == 200
        # need a second token for the conflict probe
        hub.state.registry.add_enrollment_token("second-token-PLACEHOLDER")
        code, body = hub.post("/enroll", {"runner_name": "r1", "repo": "OWNER/REPO",
                                          "enrollment_token": "second-token-PLACEHOLDER"})
        assert code == 409 and body["error"] == "already_enrolled"
    finally:
        hub.close()


def test_heartbeat_cycle_and_revoke(tmp_path):
    hub = HubFixture(tmp_path)
    try:
        code, body = hub.post("/enroll", {"runner_name": "r1", "repo": "OWNER/REPO",
                                          "enrollment_token": "test-enroll-token-PLACEHOLDER"})
        hb_token = body["heartbeat_token"]
        # fresh heartbeat -> 200
        code, body = hub.post("/heartbeat", {"runner_name": "r1", "heartbeat_token": hb_token,
                                             "last_job_seen": "run-9", "disk_ok": True, "podman_ok": True})
        assert code == 200 and body["ok"] is True
        runner = hub.state.registry.find_runner("r1")
        assert runner["last_heartbeat"] is not None
        assert runner["last_job_seen"] == "run-9"
        # wrong token -> 401
        code, body = hub.post("/heartbeat", {"runner_name": "r1", "heartbeat_token": "nope"})
        assert code == 401 and body["error"] == "unknown_or_revoked_token"
        # revoke: subsequent heartbeats must 401 (mon-enroll-01)
        hub.state.with_registry(lambda reg: reg.revoke("r1") or True)
        code, body = hub.post("/heartbeat", {"runner_name": "r1", "heartbeat_token": hb_token})
        assert code == 401 and body["error"] == "unknown_or_revoked_token"
    finally:
        hub.close()


def test_health_endpoint_shape(tmp_path):
    hub = HubFixture(tmp_path)
    try:
        code, body = hub.get("/health")
        assert code == 200
        for key in ("ok", "last_poll_at", "last_alert_at", "registered_runners",
                    "uptime_sec", "polling_enabled", "poll_interval_sec"):
            assert key in body, f"missing {key}"
        assert body["ok"] is True
        assert body["registered_runners"] == 0
    finally:
        hub.close()


def test_health_reports_polling_state_for_watchdogs(tmp_path):
    """A spoke watchdog must not read "no PAT configured" as "hub is dead".

    last_poll_at is null in two very different situations: polling disabled
    (never set) and the poll loop wedged (set, then stopped advancing).
    polling_enabled is what separates them, and poll_interval_sec is what
    lets a watcher size its staleness threshold without hardcoding one.
    """
    hub = HubFixture(tmp_path)
    try:
        # No poll thread in the fixture -> polling disabled, null is by design.
        code, body = hub.get("/health")
        assert code == 200
        assert body["polling_enabled"] is False
        assert body["last_poll_at"] is None
        assert body["poll_interval_sec"] > 0

        # Simulate a completed cycle: the timestamp must advance.
        hub.state.polling_enabled = True
        hub.state.note_poll()
        code, body = hub.get("/health")
        assert body["polling_enabled"] is True
        assert body["last_poll_at"] is not None, "note_poll did not advance /health"
    finally:
        hub.close()


def test_unknown_path_404(tmp_path):
    hub = HubFixture(tmp_path)
    try:
        code, body = hub.get("/nope")
        assert code == 404 and body["error"] == "not_found"
    finally:
        hub.close()


def main() -> int:
    import inspect
    import tempfile
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            with tempfile.TemporaryDirectory() as td:
                if "tmp_path" in inspect.signature(fn).parameters:
                    fn(Path(td))
                else:
                    fn()
            print(f"  ok   {name}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {name}: {exc}")
        except Exception as exc:
            failed += 1
            print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
