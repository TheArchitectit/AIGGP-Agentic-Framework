"""Tests for hub/monitor.py core polling (Sprint 3.1–3.3).

Dual-runnable: pytest collects test_*; `python3 tests/test_hub_monitor.py` runs them too.
Helpers live in tests/hub_monitor_harness.py.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from hub_monitor_harness import (  # noqa: E402
    FakeGitHubHandler,
    _CollectSink,
    _enroll,
    _hub_state,
    _iso,
    _start_fake_gh,
    _wire_gh,
)
from hub.config import Config  # noqa: E402
from hub.github_client import GitHubClient, parse_iso  # noqa: E402
from hub.monitor import MonitorLoop  # noqa: E402
from hub.server import HubState  # noqa: E402

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


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
