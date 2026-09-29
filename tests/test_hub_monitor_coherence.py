"""hub/monitor.py _check_spec_coherence tests (coh-int-02).

Dual-runnable. Helpers live in tests/hub_monitor_harness.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from hub_monitor_harness import (  # noqa: E402
    _start_fake_gh,
    _wire_gh,
)
from hub.config import Config  # noqa: E402
from hub.monitor import MonitorLoop  # noqa: E402
from hub.server import HubState  # noqa: E402

# --- _check_spec_coherence (coh-int-02, S6 fifth check class) ---------------


def test_check_spec_coherence_alerts_on_failure(tmp_path):
    """A coherence check-run with conclusion=failure on a watched branch
    raises coherence_failure (coh-int-02)."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.watched_branches = ["main"]
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner))

    server, port = _start_fake_gh({
        "/repos/owner/repo/commits/main?per_page=1": lambda: (200, {"sha": "cab0001"}),
        "/repos/owner/repo/commits/cab0001/check-runs?per_page=100": lambda: (200, {
            "check_runs": [
                {"name": "lint", "conclusion": "success"},
                {"name": "spec-coherence-gate", "conclusion": "failure"},
            ]}),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_spec_coherence("owner/repo")
        assert any(a[1] == "coherence_failure" and a[2] == "spec-coherence-gate"
                   for a in alerts), f"expected coherence_failure, got {alerts}"
        # The unrelated failing lint check belongs to gate_failure, not here.
        assert not any(a[1] == "coherence_failure" and a[2] == "lint"
                       for a in alerts)
    finally:
        server.shutdown()


def test_check_spec_coherence_no_alert_on_success_or_skip(tmp_path):
    """A successful (or explicitly SKIPPED) coherence check does not alert;
    unrelated checks never do."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.watched_branches = ["main"]
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner))

    server, port = _start_fake_gh({
        "/repos/owner/repo/commits/main?per_page=1": lambda: (200, {"sha": "cab0002"}),
        "/repos/owner/repo/commits/cab0002/check-runs?per_page=100": lambda: (200, {
            "check_runs": [
                {"name": "spec-coherence-gate", "conclusion": "success"},
                {"name": "spec-coherence-gate (arm64)", "conclusion": "skipping"},
                {"name": "test", "conclusion": "failure"},  # not coherence's problem
            ]}),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_spec_coherence("owner/repo")
        assert not alerts, f"unexpected alerts: {alerts}"
    finally:
        server.shutdown()


def test_check_spec_coherence_absent_is_default_deny(tmp_path):
    """No coherence check-run on a watched branch raises coherence_absent —
    the gate may not silently stop existing (default-deny, coh-int-05)."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.watched_branches = ["main"]
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner))

    server, port = _start_fake_gh({
        "/repos/owner/repo/commits/main?per_page=1": lambda: (200, {"sha": "cab0003"}),
        "/repos/owner/repo/commits/cab0003/check-runs?per_page=100": lambda: (200, {
            "check_runs": [{"name": "lint", "conclusion": "success"}]}),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_spec_coherence("owner/repo")
        assert any(a[1] == "coherence_absent" for a in alerts), \
            f"expected coherence_absent, got {alerts}"
    finally:
        server.shutdown()


def test_check_spec_coherence_timed_out_alerts(tmp_path):
    """A timed-out coherence gate is a failure, not a neutral signal."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.watched_branches = ["main"]
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner))

    server, port = _start_fake_gh({
        "/repos/owner/repo/commits/main?per_page=1": lambda: (200, {"sha": "cab0004"}),
        "/repos/owner/repo/commits/cab0004/check-runs?per_page=100": lambda: (200, {
            "check_runs": [{"name": "coherence", "conclusion": "timed_out"}]}),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_spec_coherence("owner/repo")
        assert any(a[1] == "coherence_failure" for a in alerts), alerts
    finally:
        server.shutdown()

