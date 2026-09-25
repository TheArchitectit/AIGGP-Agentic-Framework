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
import socket
import sys
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.config import Config  # noqa: E402
from hub.github_client import GitHubClient, parse_iso  # noqa: E402
from hub.monitor import MonitorLoop  # noqa: E402
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
    assert parse_iso("2026-09-14T12:00:00Z") is not None
    assert parse_iso(None) is None
    assert parse_iso("not-a-date") is None


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


# --- evaluator-image readiness (img-cycle-03) --------------------------------

def _image_state_state(tmp_path, digest, reason=None):
    """A hub state with one enrolled runner carrying the given image state."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    state = HubState(config)
    state.registry.add_enrollment_token("tok")
    state.registry.consume_enrollment_token("tok")
    runner = state.registry.enroll("r1", "owner/repo", ["devgate"], "dell-u2")
    runner["image_digest"] = digest
    runner["image_reason"] = reason
    runner["last_heartbeat"] = _iso(datetime.now(timezone.utc))
    state.registry.save()
    return state, runner


class _CollectSink:
    def __init__(self):
        self.alerts = []

    def raise_alert(self, repo, check_class, runner, detail):
        self.alerts.append((repo, check_class, runner, detail))


def test_check_image_readiness_alerts_on_a_host_that_cannot_serve_the_pin(tmp_path):
    """A host with no image is not ready to gate, and the reason is carried."""
    state, runner = _image_state_state(tmp_path, None, "podman not on PATH")
    sink = _CollectSink()
    monitor = MonitorLoop(state, alert_sink=sink)
    monitor._check_image_readiness("owner/repo", [runner])

    assert len(sink.alerts) == 1, sink.alerts
    repo, check_class, name, detail = sink.alerts[0]
    assert check_class == "runner_image_missing"
    assert name == "r1" and repo == "owner/repo"
    assert "podman not on PATH" in detail, detail


def test_check_image_readiness_stays_quiet_for_a_converged_host(tmp_path):
    """The mirror case, or the check would be an alert on every healthy host."""
    ref = "ghcr.io/owner/repo/devgate-coherence@sha256:" + "a" * 64
    state, runner = _image_state_state(tmp_path, ref)
    sink = _CollectSink()
    monitor = MonitorLoop(state, alert_sink=sink)
    monitor._check_image_readiness("owner/repo", [runner])
    assert sink.alerts == [], sink.alerts


def test_check_image_readiness_reports_an_unreported_image_as_unreported(tmp_path):
    """No digest AND no reason must still alert — and say so, not say nothing.

    This is the state every already-enrolled host is in: its helper predates
    the cycle, so the registry holds no image keys at all. Rendering that as
    silence would count the whole fleet as ready to gate.
    """
    state, runner = _image_state_state(tmp_path, None, None)
    sink = _CollectSink()
    monitor = MonitorLoop(state, alert_sink=sink)
    monitor._check_image_readiness("owner/repo", [runner])

    assert len(sink.alerts) == 1, sink.alerts
    detail = sink.alerts[0][3]
    # The SENTENCE has to differ from a host that reported a fault, not just a
    # trailing parenthetical: "unknown" and "cannot serve" are different facts
    # needing different actions, and an operator skimming a fleet view reads
    # the first clause. Both still name what is wrong with the gate.
    assert "has not reported an image state" in detail, detail
    assert "cannot serve the pinned evaluator image" in detail, detail


def test_a_rate_limited_hub_still_alerts_about_a_missing_image(tmp_path):
    """Why this is not folded into _check_runner_status.

    That check returns early when the runners API call fails, so an image
    deficiency raised there would go silent during a rate limit — exactly when
    an operator is staring at a fleet view that says everything is fine. The
    API here answers 403 on every attempt, and the image alert must still
    arrive.
    """
    state, runner = _image_state_state(tmp_path, None, "store mismatch: x != y")
    sink = _CollectSink()

    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/runners": lambda: (403, {"message": "rate limited"})
    })
    try:
        monitor = MonitorLoop(state, alert_sink=sink)
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor.client.backoff_max = 0
        monitor.poll_cycle()
    finally:
        server.shutdown()

    classes = [a[1] for a in sink.alerts]
    assert "runner_image_missing" in classes, (
        f"the image deficiency was silenced by the API failure: {sink.alerts}")


# --- fleet scan state rendering (secret-scan-07) -----------------------------

def test_poll_cycle_reports_scan_state_while_the_api_is_unreachable(tmp_path):
    """The seam, the attribution, and the ordering this check exists for.

    Pins that poll_cycle DISPATCHES the check (a wiring that exists and is never
    called passes every direct-method test) and that two hosts sharing one
    check_class are told apart by runner. The port here is CLOSED, not rate
    limited: the client catches HTTPError but NOT URLError, so a refused
    connection raises out of `_check_runner_status` into poll_cycle's per-repo
    handler and aborts every check after it — reading only the registry keeps
    this check alive through that, but only if it runs before the network calls.
    """
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    dead_port = probe.getsockname()[1]
    probe.close()  # nothing listens there now: a real ECONNREFUSED
    state, r1 = _image_state_state(tmp_path, None, None)
    r2 = state.registry.enroll("r2", "owner/repo", ["devgate"], "ucs03")
    r2["scan_state"] = {"repos": [{"name": "alpha", "state": "findings",
                                   "findings": 2, "uncovered": 1}],
                        "unreadable": None}
    state.registry.save()
    sink = _CollectSink()
    monitor = MonitorLoop(state, alert_sink=sink)
    monitor.client.api_base = f"http://127.0.0.1:{dead_port}"
    monitor.client.backoff_max = 0
    monitor.poll_cycle()
    # Compare the prefix: tuple equality includes LENGTH, so a 3-tuple is never
    # `in` a list of 4-tuples — the assertion would hold for no wiring at all.
    got = [(repo, cls, who) for repo, cls, who, _ in sink.alerts]
    assert ("owner/repo", "runner_scan_unknown", "r1") in got, sink.alerts
    assert ("owner/repo", "runner_scan_findings", "r2") in got, sink.alerts


def main() -> int:
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))


if __name__ == "__main__":
    main()
