"""Reproduce three synthetic monitor observations without network access."""
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

from hub.monitor import MonitorLoop


class FakeClient:
    def __init__(self, handler):
        self.handler = handler
        self.paths = []

    def get_with_backoff(self, path):
        self.paths.append(path)
        return self.handler(path)


def make_monitor(handler):
    monitor = MonitorLoop.__new__(MonitorLoop)
    monitor.config = SimpleNamespace(
        queue_threshold_min=30,
        drift_grace_min=10,
        drift_workflow_match="drift",
    )
    monitor.client = FakeClient(handler)
    alerts = []

    def record_alert(repo, kind, runner, detail):
        alerts.append({"repo": repo, "kind": kind, "runner": runner, "detail": detail})

    monitor._raise_alert = record_alert
    return monitor, alerts


def as_utc(value):
    return value.isoformat().replace("+00:00", "Z")


def main():
    now = datetime.now(timezone.utc)
    queued_at = as_utc(now - timedelta(minutes=45))

    def queue_response(path):
        return 200, {"workflow_runs": [
            {"id": 314, "name": "fixture-ci", "created_at": queued_at}
        ]}

    monitor, registered_alerts = make_monitor(queue_response)
    monitor._check_queue_drain(
        "example/repo", [{"name": "fixture", "labels": ["devgate"]}]
    )
    monitor, empty_alerts = make_monitor(queue_response)
    monitor._check_queue_drain("example/repo", [])
    assert registered_alerts == empty_alerts
    assert registered_alerts[0]["runner"] == "314"
    assert "devgate" not in registered_alerts[0]["detail"]

    completed_at = as_utc(now - timedelta(hours=2))

    def drift_response(path):
        if path.endswith("/workflows?per_page=100"):
            return 200, {"workflows": [{"id": 42, "name": "drift"}]}
        return 200, {"workflow_runs": [
            {"conclusion": "success", "completed_at": completed_at}
        ]}

    monitor, drift_alerts = make_monitor(drift_response)
    monitor._check_drift_scan("example/repo")
    drift_paths = monitor.client.paths.copy()
    assert not drift_alerts

    sha = "0123456789abcdef" * 2 + "01234567"

    def gate_response(path):
        if "/check-runs?" not in path:
            return 200, {"sha": sha}
        return 200, {"check_runs": [{"name": "fixture-gate", "conclusion": "failure"}]}

    monitor, gate_alerts = make_monitor(gate_response)
    monitor._watched_branches = lambda repo: ["main"]
    monitor._check_gate_results("example/repo")
    assert len(gate_alerts) == 1
    assert sha[:8] in gate_alerts[0]["detail"]
    assert sha not in gate_alerts[0]["detail"]

    results = {
        "queue_runner_list": {
            "operation": "MonitorLoop._check_queue_drain",
            "fixture": "45-minute-old run, repeated with devgate runner and empty runner list",
            "registered_runner_alerts": registered_alerts,
            "empty_runner_alerts": empty_alerts,
            "interpretation": "same alert for both inputs; alert contains run id and age but no label",
        },
        "drift_hourly": {
            "operation": "MonitorLoop._check_drift_scan",
            "fixture": "successful completed run two hours ago, assessed against a hypothetical hourly schedule with ten-minute grace",
            "events": drift_alerts,
            "queried_paths": drift_paths,
            "interpretation": "no alert; source uses 24 hours plus grace and does not read a schedule period",
        },
        "gate_commit": {
            "operation": "MonitorLoop._check_gate_results",
            "fixture_sha": sha,
            "events": gate_alerts,
            "interpretation": "detail includes eight-character SHA prefix",
        },
    }
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
