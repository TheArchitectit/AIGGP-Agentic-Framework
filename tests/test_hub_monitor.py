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

def _wire_gh(monitor: MonitorLoop, port: int) -> None:
    """Point a monitor at the fake server, with backoff off so retries do not sleep."""
    monitor.client.api_base = f"http://127.0.0.1:{port}"
    monitor.client.backoff_max = 0

def _hub_state(tmp_path) -> HubState:
    """A HubState whose data dir is under tmp_path, so no test writes to the real one."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    return HubState(config)

def _enroll(state: HubState, name: str, repo: str, host: str = "host1"):
    """Consume a one-shot enrollment token and return the enrolled runner dict.

    The token value is never asserted on, only that enrollment went through the
    one-shot path — so it is derived from the name rather than repeated at each
    call site.
    """
    token = f"tok-{name}"
    state.registry.add_enrollment_token(token)
    state.registry.consume_enrollment_token(token)
    return state.registry.enroll(name, repo, ["devgate"], host)

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_parse_iso():
    assert parse_iso("2026-09-14T12:00:00Z") is not None
    assert parse_iso(None) is None
    assert parse_iso("not-a-date") is None

def test_the_monitor_runs_the_transport_the_tests_pin():
    """One GitHubClient, not two.

    monitor.py had a second copy of the transport inlined into it, SHADOWING
    the hub.github_client import: test_github_client_backoff below constructs
    the imported class and passes while the monitor ran the other one. Both
    were named GitHubClient, so nothing failed. Identity, not behaviour, is the
    assertion — an identical-behaving copy is still the defect this pins.
    """
    import hub.monitor as monitor_module
    from hub import github_client as transport

    assert monitor_module.GitHubClient is transport.GitHubClient, \
        "hub/monitor.py binds a different GitHubClient than hub/github_client.py " \
        "defines — a second copy is shadowing the import again"

def test_refresh_token_rereads_the_file_and_keeps_the_token_on_failure(tmp_path):
    """The rotation feature, on the class that actually runs.

    The failure half must force a real READ failure: an ABSENT path never
    reaches the except (isfile short-circuits) and a DIRECTORY reads as "" on
    Linux rather than raising. Measured — a mutation blanking the token on
    every read error survived both. At mode 0o000 the path IS a file and
    read_text raises PermissionError, the one shape that reaches the branch.
    """
    tok = tmp_path / "github_token.txt"
    tok.write_text("ghs_first\n")
    client = GitHubClient(api_base="http://127.0.0.1:1", token="stale",
                          token_file=str(tok))
    client.refresh_token()
    assert client.token == "ghs_first", "rotation did not take effect"

    if os.geteuid() != 0:  # root ignores the mode bits; the branch is unreachable
        tok.chmod(0o000)
        client.refresh_token()
        assert client.token == "ghs_first", \
            "an unreadable token file dropped the token — every check in that " \
            "cycle would 401 instead of reusing the last known-good token"
        tok.chmod(0o600)  # let tmp_path cleanup remove it

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
    state = _hub_state(tmp_path)

    # Enroll a runner with a stale heartbeat.
    runner = _enroll(state, "r1", "owner/repo", "host1")
    # Backdate the heartbeat by 3 intervals (stale: > 2 * 300s).
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=16)
    runner["last_heartbeat"] = _iso(stale_time)
    state.registry.save()

    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/runners": lambda: (200, {"runners": [
            {"name": "r1", "status": "online"}]})
    })
    try:
        sink = _CollectSink()
        monitor = MonitorLoop(state, alert_sink=sink)
        _wire_gh(monitor, port)
        monitor._check_runner_status("owner/repo", [runner])
        assert any(a[1] == "runner_offline" for a in sink.alerts), \
            f"expected runner_offline alert, got {sink.alerts}"
    finally:
        server.shutdown()

def test_check_runner_status_no_alert_when_healthy(tmp_path):
    """Healthy runner (API online + fresh heartbeat) raises no alert."""
    state = _hub_state(tmp_path)

    runner = _enroll(state, "r1", "owner/repo", "host1")
    # Fresh heartbeat (just now).
    runner["last_heartbeat"] = _iso(datetime.now(timezone.utc))
    state.registry.save()

    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/runners": lambda: (200, {"runners": [
            {"name": "r1", "status": "online"}]})
    })
    try:
        sink = _CollectSink()
        monitor = MonitorLoop(state, alert_sink=sink)
        _wire_gh(monitor, port)
        monitor._check_runner_status("owner/repo", [runner])
        assert not sink.alerts, f"unexpected alerts: {sink.alerts}"
    finally:
        server.shutdown()

def test_check_queue_drain_alerts_on_stalled_run(tmp_path):
    """A queued run older than the threshold raises an alert (mon-queue-01)."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.queue_threshold_min = 30.0
    state = HubState(config)

    # A run queued 45 minutes ago (exceeds 30-min threshold).
    old_time = datetime.now(timezone.utc) - timedelta(minutes=45)
    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/runs?per_page=50&status=queued": lambda: (200, {
            "workflow_runs": [
                {"run_id": 12345, "name": "CI", "created_at": _iso(old_time)}
            ]})
    })
    try:
        sink = _CollectSink()
        monitor = MonitorLoop(state, alert_sink=sink)
        _wire_gh(monitor, port)
        monitor._check_queue_drain("owner/repo", [{"name": "r1", "labels": ["devgate"]}])
        assert any(a[1] == "queue_stall" for a in sink.alerts), \
            f"expected queue_stall, got {sink.alerts}"
    finally:
        server.shutdown()

def test_check_queue_drain_no_alert_for_fresh_run(tmp_path):
    """A queued run younger than the threshold does NOT alert."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.queue_threshold_min = 30.0
    state = HubState(config)

    # A run queued 5 minutes ago (under threshold).
    fresh_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/runs?per_page=50&status=queued": lambda: (200, {
            "workflow_runs": [
                {"run_id": 12345, "name": "CI", "created_at": _iso(fresh_time)}
            ]})
    })
    try:
        sink = _CollectSink()
        monitor = MonitorLoop(state, alert_sink=sink)
        _wire_gh(monitor, port)
        monitor._check_queue_drain("owner/repo", [{"name": "r1", "labels": ["devgate"]}])
        assert not sink.alerts, f"unexpected alerts: {sink.alerts}"
    finally:
        server.shutdown()

def test_check_gate_results_alerts_on_failure(tmp_path):
    """A check-run with conclusion=failure on a watched branch alerts (mon-gates-01)."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.watched_branches = ["main"]
    state = HubState(config)

    server, port = _start_fake_gh({
        "/repos/owner/repo/commits/main?per_page=1": lambda: (200, {"sha": "abc1234"}),
        "/repos/owner/repo/commits/abc1234/check-runs?per_page=100": lambda: (200, {
            "check_runs": [
                {"name": "lint", "conclusion": "success"},
                {"name": "test", "conclusion": "failure"},
            ]}),
    })
    try:
        sink = _CollectSink()
        monitor = MonitorLoop(state, alert_sink=sink)
        _wire_gh(monitor, port)
        monitor._check_gate_results("owner/repo", "owner")
        assert any(a[1] == "gate_failure" and a[2] == "test" for a in sink.alerts), \
            f"expected gate_failure for 'test', got {sink.alerts}"
    finally:
        server.shutdown()

def test_check_gate_results_no_alert_on_success(tmp_path):
    """All-success check-runs do NOT alert."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.watched_branches = ["main"]
    state = HubState(config)

    server, port = _start_fake_gh({
        "/repos/owner/repo/commits/main?per_page=1": lambda: (200, {"sha": "abc1234"}),
        "/repos/owner/repo/commits/abc1234/check-runs?per_page=100": lambda: (200, {
            "check_runs": [
                {"name": "lint", "conclusion": "success"},
                {"name": "test", "conclusion": "success"},
            ]}),
    })
    try:
        sink = _CollectSink()
        monitor = MonitorLoop(state, alert_sink=sink)
        _wire_gh(monitor, port)
        monitor._check_gate_results("owner/repo", "owner")
        assert not sink.alerts, f"unexpected alerts: {sink.alerts}"
    finally:
        server.shutdown()

def test_check_drift_scan_alerts_on_overdue(tmp_path):
    """A drift scan older than 24h+grace raises an alert (mon-drift-01)."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.drift_grace_min = 10.0
    config.drift_workflow_match = "drift"
    state = HubState(config)

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
        sink = _CollectSink()
        monitor = MonitorLoop(state, alert_sink=sink)
        _wire_gh(monitor, port)
        monitor._check_drift_scan("owner/repo", "owner")
        assert any(a[1] == "drift_overdue" for a in sink.alerts), \
            f"expected drift_overdue, got {sink.alerts}"
    finally:
        server.shutdown()

def test_check_drift_scan_alerts_on_failed(tmp_path):
    """A failed drift scan raises an alert (mon-drift-01)."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.drift_grace_min = 10.0
    config.drift_workflow_match = "drift"
    state = HubState(config)

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
        sink = _CollectSink()
        monitor = MonitorLoop(state, alert_sink=sink)
        _wire_gh(monitor, port)
        monitor._check_drift_scan("owner/repo", "owner")
        assert any(a[1] == "drift_failed" for a in sink.alerts), \
            f"expected drift_failed, got {sink.alerts}"
    finally:
        server.shutdown()

def test_check_drift_scan_no_workflow_found(tmp_path):
    """No drift-scan workflow → alert (mon-drift-01)."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.drift_workflow_match = "drift"
    state = HubState(config)

    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/workflows?per_page=100": lambda: (200, {
            "workflows": [{"id": 1, "name": "CI"}]}),
    })
    try:
        sink = _CollectSink()
        monitor = MonitorLoop(state, alert_sink=sink)
        _wire_gh(monitor, port)
        monitor._check_drift_scan("owner/repo", "owner")
        assert any(a[1] == "drift_overdue" for a in sink.alerts), \
            f"expected drift_overdue (no workflow), got {sink.alerts}"
    finally:
        server.shutdown()

def test_poll_cycle_groups_by_repo(tmp_path):
    """poll_cycle groups runners by repo and polls each once."""
    state = _hub_state(tmp_path)

    # Two runners in the same repo.
    r1 = _enroll(state, "r1", "owner/repo", "h1")
    r1["last_heartbeat"] = _iso(datetime.now(timezone.utc))

    r2 = _enroll(state, "r2", "owner/repo", "h2")
    r2["last_heartbeat"] = _iso(datetime.now(timezone.utc))

    # A runner in a different repo.
    r3 = _enroll(state, "r3", "owner/other", "h3")
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

    # Build routes for both repos. Every path the cycle walks, so a check that
    # gains a new endpoint fails here as a 404 rather than silently passing.
    routes = {}
    paths = ["/actions/runners", "/actions/runs?per_page=50&status=queued",
             "/commits/main?per_page=1", "/commits/abc/check-runs?per_page=100",
             "/actions/workflows?per_page=100", "/actions/workflows/1/runs?per_page=1"]
    for repo in ("owner/repo", "owner/other"):
        for path in paths:
            routes[f"/repos/{repo}{path}"] = make_handler(f"/repos/{repo}{path}")

    server, port = _start_fake_gh(routes)
    try:
        monitor = MonitorLoop(state)
        _wire_gh(monitor, port)
        monitor.poll_cycle()
        # Both repos should have been polled.
        assert any("owner/repo" in c for c in calls), f"owner/repo not polled: {calls}"
        assert any("owner/other" in c for c in calls), f"owner/other not polled: {calls}"
    finally:
        server.shutdown()

# --- evaluator-image readiness (img-cycle-03) --------------------------------

def _image_state_state(tmp_path, digest, reason=None):
    """A hub state with one enrolled runner carrying the given image state."""
    state = _hub_state(tmp_path)
    runner = _enroll(state, "r1", "owner/repo", "dell-u2")
    runner["image_digest"] = digest
    runner["image_reason"] = reason
    runner["last_heartbeat"] = _iso(datetime.now(timezone.utc))
    state.registry.save()
    return state, runner

class _CollectSink:
    """Records alerts as (repo, check_class, runner, detail).

    Every test here needs only `check_class` (or the runner name); both are
    reachable from the 4-tuple, so one sink serves the whole file instead of a
    near-identical local class in each test.
    """

    def __init__(self):
        self.alerts = []

    def raise_alert(self, repo, check_class, runner, detail):
        self.alerts.append((repo, check_class, runner, detail))

    @property
    def classes(self) -> list[str]:
        return [a[1] for a in self.alerts]

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
    r2 = _enroll(state, "r2", "owner/repo", "ucs03")
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
