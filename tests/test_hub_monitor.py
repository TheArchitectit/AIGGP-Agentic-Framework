"""Tests for hub/monitor.py (Sprint 3.1–3.3): GitHub polling loop.

Uses a fake GitHub API server (stdlib http.server) so no real network calls
are made. Verifies:
  - runner online detection (API status + heartbeat freshness)
  - queue-drain detection (queued run older than threshold)
  - gate-result tracking (check-run conclusion failure/timed_out)
  - drift-scan recency (overdue or failed scan)
  - rate-limit backoff on 403/429

Dual-runnable: pytest collects test_*; `python3 tests/test_hub_monitor.py` runs them too.
"""
import json
import os
import sys
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.config import Config  # noqa: E402
from hub.monitor import GitHubClient, MonitorLoop, _parse_iso  # noqa: E402
from hub.server import HubState  # noqa: E402


# ---------------------------------------------------------------------------
# Fake GitHub API server (per-instance routes to avoid cross-test pollution)
# ---------------------------------------------------------------------------

class FakeGitHubHandler(BaseHTTPRequestHandler):
    """Routes GitHub API paths to canned responses configured per-server."""

    def log_message(self, fmt, *args):
        pass  # silence

    def do_GET(self):
        routes: dict = self.server.routes  # type: ignore[attr-defined]
        handler = routes.get(self.path)
        if handler is None:
            self._respond(404, {"message": "not found"})
            return
        status, body = handler()
        self._respond(status, body)

    def _respond(self, status: int, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _start_fake_gh(routes: dict) -> tuple[ThreadingHTTPServer, int]:
    """Start a fake GitHub API server with the given routes. Returns (server, port)."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeGitHubHandler)
    server.routes = routes  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_parse_iso():
    assert _parse_iso("2026-09-14T12:00:00Z") is not None
    assert _parse_iso(None) is None
    assert _parse_iso("not-a-date") is None


def test_github_client_backoff():
    """GitHubClient backs off on 403/429 and eventually returns the body."""
    call_count = {"n": 0}

    def flaky_handler():
        call_count["n"] += 1
        if call_count["n"] < 3:
            return (403, {"message": "rate limited", "retry_after": 1})
        return (200, {"ok": True})

    server, port = _start_fake_gh({"/repos/o/r/actions/runners": flaky_handler})
    try:
        client = GitHubClient(api_base=f"http://127.0.0.1:{port}", token="test", backoff_max=5)
        result = client.get_with_backoff("/repos/o/r/actions/runners", max_retries=3)
        assert result is not None
        status, body = result
        assert status == 200
        assert call_count["n"] == 3
    finally:
        server.shutdown()


def test_check_runner_status_alerts_on_stale_heartbeat(tmp_path):
    """Runner with stale heartbeat raises an alert (mon-online-01)."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    state = HubState(config)

    # Enroll a runner with a stale heartbeat.
    state.registry.add_enrollment_token("tok")
    state.registry.consume_enrollment_token("tok")
    runner = state.registry.enroll("r1", "owner/repo", ["devgate"], "host1")
    # Backdate the heartbeat by 3 intervals (stale: > 2 * 300s).
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=16)
    runner["last_heartbeat"] = _iso(stale_time)
    state.registry.save()

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner))

    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/runners": lambda: (200, {"runners": [
            {"name": "r1", "status": "online"}]})
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_runner_status("owner/repo", [runner])
        assert any(a[1] == "runner_offline" for a in alerts), \
            f"expected runner_offline alert, got {alerts}"
    finally:
        server.shutdown()


def test_check_runner_status_no_alert_when_healthy(tmp_path):
    """Healthy runner (API online + fresh heartbeat) raises no alert."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    state = HubState(config)

    state.registry.add_enrollment_token("tok")
    state.registry.consume_enrollment_token("tok")
    runner = state.registry.enroll("r1", "owner/repo", ["devgate"], "host1")
    # Fresh heartbeat (just now).
    runner["last_heartbeat"] = _iso(datetime.now(timezone.utc))
    state.registry.save()

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner))

    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/runners": lambda: (200, {"runners": [
            {"name": "r1", "status": "online"}]})
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_runner_status("owner/repo", [runner])
        assert not alerts, f"unexpected alerts: {alerts}"
    finally:
        server.shutdown()


def test_check_queue_drain_alerts_on_stalled_run(tmp_path):
    """A queued run older than the threshold raises an alert (mon-queue-01)."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.queue_threshold_min = 30.0
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner))

    # A run queued 45 minutes ago (exceeds 30-min threshold).
    old_time = datetime.now(timezone.utc) - timedelta(minutes=45)
    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/runs?per_page=50&status=queued": lambda: (200, {
            "workflow_runs": [
                {"run_id": 12345, "name": "CI", "created_at": _iso(old_time)}
            ]})
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_queue_drain("owner/repo", [{"name": "r1", "labels": ["devgate"]}])
        assert any(a[1] == "queue_stall" for a in alerts), \
            f"expected queue_stall, got {alerts}"
    finally:
        server.shutdown()


def test_check_queue_drain_no_alert_for_fresh_run(tmp_path):
    """A queued run younger than the threshold does NOT alert."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.queue_threshold_min = 30.0
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner))

    # A run queued 5 minutes ago (under threshold).
    fresh_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/runs?per_page=50&status=queued": lambda: (200, {
            "workflow_runs": [
                {"run_id": 12345, "name": "CI", "created_at": _iso(fresh_time)}
            ]})
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_queue_drain("owner/repo", [{"name": "r1", "labels": ["devgate"]}])
        assert not alerts, f"unexpected alerts: {alerts}"
    finally:
        server.shutdown()


def test_check_gate_results_alerts_on_failure(tmp_path):
    """A check-run with conclusion=failure on a watched branch alerts (mon-gates-01)."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.watched_branches = ["main"]
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner))

    server, port = _start_fake_gh({
        "/repos/owner/repo/commits/main?per_page=1": lambda: (200, {"sha": "abc1234"}),
        "/repos/owner/repo/commits/abc1234/check-runs?per_page=100": lambda: (200, {
            "check_runs": [
                {"name": "lint", "conclusion": "success"},
                {"name": "test", "conclusion": "failure"},
            ]}),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_gate_results("owner/repo", "owner")
        assert any(a[1] == "gate_failure" and a[2] == "test" for a in alerts), \
            f"expected gate_failure for 'test', got {alerts}"
    finally:
        server.shutdown()


def test_check_gate_results_no_alert_on_success(tmp_path):
    """All-success check-runs do NOT alert."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.watched_branches = ["main"]
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner))

    server, port = _start_fake_gh({
        "/repos/owner/repo/commits/main?per_page=1": lambda: (200, {"sha": "abc1234"}),
        "/repos/owner/repo/commits/abc1234/check-runs?per_page=100": lambda: (200, {
            "check_runs": [
                {"name": "lint", "conclusion": "success"},
                {"name": "test", "conclusion": "success"},
            ]}),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_gate_results("owner/repo", "owner")
        assert not alerts, f"unexpected alerts: {alerts}"
    finally:
        server.shutdown()


def test_check_drift_scan_alerts_on_overdue(tmp_path):
    """A drift scan older than 24h+grace raises an alert (mon-drift-01)."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.drift_grace_min = 10.0
    config.drift_workflow_match = "drift"
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner))

    # Last drift scan completed 30 hours ago (exceeds 24h + 10min grace).
    old_time = datetime.now(timezone.utc) - timedelta(hours=30)
    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/workflows?per_page=100": lambda: (200, {
            "workflows": [{"id": 99, "name": "drift-scan"}]}),
        "/repos/owner/repo/actions/workflows/99/runs?per_page=1": lambda: (200, {
            "workflow_runs": [
                {"conclusion": "success", "completed_at": _iso(old_time)}
            ]}),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_drift_scan("owner/repo", "owner")
        assert any(a[1] == "drift_overdue" for a in alerts), \
            f"expected drift_overdue, got {alerts}"
    finally:
        server.shutdown()


def test_check_drift_scan_alerts_on_failed(tmp_path):
    """A failed drift scan raises an alert (mon-drift-01)."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.drift_grace_min = 10.0
    config.drift_workflow_match = "drift"
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner))

    recent_time = datetime.now(timezone.utc) - timedelta(hours=1)
    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/workflows?per_page=100": lambda: (200, {
            "workflows": [{"id": 99, "name": "drift-scan"}]}),
        "/repos/owner/repo/actions/workflows/99/runs?per_page=1": lambda: (200, {
            "workflow_runs": [
                {"conclusion": "failure", "completed_at": _iso(recent_time)}
            ]}),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_drift_scan("owner/repo", "owner")
        assert any(a[1] == "drift_failed" for a in alerts), \
            f"expected drift_failed, got {alerts}"
    finally:
        server.shutdown()


def test_check_drift_scan_no_workflow_found(tmp_path):
    """No drift-scan workflow → alert (mon-drift-01)."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.drift_workflow_match = "drift"
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner))

    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/workflows?per_page=100": lambda: (200, {
            "workflows": [{"id": 1, "name": "CI"}]}),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_drift_scan("owner/repo", "owner")
        assert any(a[1] == "drift_overdue" for a in alerts), \
            f"expected drift_overdue (no workflow), got {alerts}"
    finally:
        server.shutdown()


def test_poll_cycle_groups_by_repo(tmp_path):
    """poll_cycle groups runners by repo and polls each once."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    state = HubState(config)

    # Two runners in the same repo.
    state.registry.add_enrollment_token("tok1")
    state.registry.consume_enrollment_token("tok1")
    r1 = state.registry.enroll("r1", "owner/repo", ["devgate"], "h1")
    r1["last_heartbeat"] = _iso(datetime.now(timezone.utc))

    state.registry.add_enrollment_token("tok2")
    state.registry.consume_enrollment_token("tok2")
    r2 = state.registry.enroll("r2", "owner/repo", ["devgate"], "h2")
    r2["last_heartbeat"] = _iso(datetime.now(timezone.utc))

    # A runner in a different repo.
    state.registry.add_enrollment_token("tok3")
    state.registry.consume_enrollment_token("tok3")
    r3 = state.registry.enroll("r3", "owner/other", ["devgate"], "h3")
    r3["last_heartbeat"] = _iso(datetime.now(timezone.utc))

    calls: list[str] = []

    def make_handler(path: str):
        def handler():
            calls.append(path)
            if "/actions/runners" in path:
                return (200, {"runners": [
                    {"name": "r1", "status": "online"},
                    {"name": "r2", "status": "online"},
                    {"name": "r3", "status": "online"}]})
            if "/actions/runs" in path and "queued" in path:
                return (200, {"workflow_runs": []})
            if "/commits/" in path and "check-runs" not in path:
                return (200, {"sha": "abc"})
            if "check-runs" in path:
                return (200, {"check_runs": []})
            if "/actions/workflows?" in path:
                return (200, {"workflows": [{"id": 1, "name": "drift-scan"}]})
            if "/runs?per_page=1" in path:
                return (200, {"workflow_runs": [
                    {"conclusion": "success",
                     "completed_at": _iso(datetime.now(timezone.utc))}]})
            return (404, {})
        return handler

    # Build routes for both repos.
    routes = {}
    for repo in ("owner/repo", "owner/other"):
        routes[f"/repos/{repo}/actions/runners"] = make_handler(f"/repos/{repo}/actions/runners")
        routes[f"/repos/{repo}/actions/runs?per_page=50&status=queued"] = make_handler(
            f"/repos/{repo}/actions/runs?per_page=50&status=queued")
        routes[f"/repos/{repo}/commits/main?per_page=1"] = make_handler(f"/repos/{repo}/commits/main?per_page=1")
        routes[f"/repos/{repo}/commits/abc/check-runs?per_page=100"] = make_handler(
            f"/repos/{repo}/commits/abc/check-runs?per_page=100")
        routes[f"/repos/{repo}/actions/workflows?per_page=100"] = make_handler(
            f"/repos/{repo}/actions/workflows?per_page=100")
        routes[f"/repos/{repo}/actions/workflows/1/runs?per_page=1"] = make_handler(
            f"/repos/{repo}/actions/workflows/1/runs?per_page=1")

    server, port = _start_fake_gh(routes)
    try:
        monitor = MonitorLoop(state)
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor.poll_cycle()
        # Both repos should have been polled.
        assert any("owner/repo" in c for c in calls), f"owner/repo not polled: {calls}"
        assert any("owner/other" in c for c in calls), f"owner/other not polled: {calls}"
    finally:
        server.shutdown()


def main() -> int:
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))


if __name__ == "__main__":
    main()
