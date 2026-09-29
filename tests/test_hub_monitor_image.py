"""hub/monitor.py evaluator-image readiness, fleet scan state, queue-stall keys.

Dual-runnable. Helpers live in tests/hub_monitor_harness.py.
"""
import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from hub_monitor_harness import (  # noqa: E402
    _CollectSink,
    _enroll,
    _hub_state,
    _iso,
    _start_fake_gh,
    _wire_gh,
)
from hub.config import Config  # noqa: E402
from hub.github_client import parse_iso  # noqa: E402
from hub.monitor import MonitorLoop  # noqa: E402
from hub.server import HubState  # noqa: E402

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


def test_watched_branch_default_sentinel_resolves_via_api(tmp_path):
    """F6: the 'default' config sentinel is resolved to the repo's real
    default branch each cycle. The old literal 404'd every gate-results
    check on a default deployment while looking healthy."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.watched_branches = ["default"]  # the shipped default
    state = HubState(config)
    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner))

    server, port = _start_fake_gh({
        "/repos/owner/repo": lambda: (200, {"default_branch": "trunk"}),
        "/repos/owner/repo/commits/trunk?per_page=1": lambda: (200, {"sha": "abc1234"}),
        "/repos/owner/repo/commits/abc1234/check-runs?per_page=100": lambda: (200, {
            "check_runs": [{"name": "test", "conclusion": "failure"}]}),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_gate_results("owner/repo")
        assert any(a[1] == "gate_failure" for a in alerts), \
            f"sentinel must resolve to the real default branch, got {alerts}"
    finally:
        server.shutdown()


def test_watched_branch_unresolvable_skips_loudly(tmp_path):
    """F6: an unresolvable default branch skips the check class with a
    warning — never a crash, and never silently reported as clean."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.watched_branches = ["default"]
    state = HubState(config)
    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner))

    server, port = _start_fake_gh({})  # no routes: /repos/owner/repo -> 404
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_gate_results("owner/repo")  # must not raise
        assert alerts == []
    finally:
        server.shutdown()


def test_queue_stall_uses_run_id_field(tmp_path):
    """F5: the workflow-run identifier is `id` — alerts must key on it so
    distinct stalled runs are distinct, not collapsed onto one '?' key."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.queue_threshold_min = 30.0
    state = HubState(config)
    keys = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            keys.append(runner)

    old = _iso(datetime.now(timezone.utc) - timedelta(minutes=45))
    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/runs?per_page=50&status=queued": lambda: (200, {
            "workflow_runs": [
                {"id": 111, "created_at": old, "name": "ci"},
                {"id": 222, "created_at": old, "name": "deploy"},
            ]}),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_queue_drain("owner/repo", [])
        # The alert's runner field is a name string keyed on run `id`; two
        # distinct ids must stay two distinct keys.
        assert keys == ["111", "222"], f"distinct run ids expected, got {keys}"
    finally:
        server.shutdown()


# --- served-vs-record pin divergence (img-cycle-05) ----------------------------

def test_poll_cycle_dispatches_the_pin_divergence_check(tmp_path):
    """A wiring that exists and is never called passes every direct-method test.
    Pins that poll_cycle actually DISPATCHES _check_image_pin_divergence.

    The port is CLOSED: the client catches HTTPError but not URLError, so a
    refused connection raises out of `_check_runner_status` into poll_cycle's
    per-repo handler and aborts every check after it. The call sits BEFORE the
    network checks (same placement as `_check_image_readiness`), so a registry-
    driven alert must still arrive — and the only way it arrives is if the
    dispatch is wired.
    """
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    dead_port = probe.getsockname()[1]
    probe.close()  # nothing listens there now: a real ECONNREFUSED
    state, runner = _image_state_state(tmp_path, None, None)
    detail = ("served ghcr.io/o/r/devgate-coherence:main is sha256:b..b "
              "but the record is sha256:a..a — a re-pin is due")
    runner["image_pin_divergence"] = detail
    state.registry.save()
    sink = _CollectSink()
    monitor = MonitorLoop(state, alert_sink=sink)
    monitor.client.api_base = f"http://127.0.0.1:{dead_port}"
    monitor.client.backoff_max = 0
    monitor.poll_cycle()
    got = [(repo, cls, who) for repo, cls, who, _ in sink.alerts]
    assert ("owner/repo", "image_pin_divergence", "?") in got, sink.alerts


def test_check_image_pin_divergence_alerts_once_per_repo_as_a_repository_fact(tmp_path):
    """Divergence is a fact about the repository (D6), so the alert is keyed on
    runner "?" — N hosts reporting the same re-pin is one ticket, not N."""
    state = _hub_state(tmp_path)
    r1 = _enroll(state, "r1", "owner/repo", "dell-u2")
    r2 = _enroll(state, "r2", "owner/repo", "ucs03")
    detail = ("served ghcr.io/o/r/devgate-coherence:main is sha256:b..b "
              "but the record is sha256:a..a — a re-pin is due")
    r1["image_pin_divergence"] = detail
    r2["image_pin_divergence"] = detail
    state.registry.save()
    sink = _CollectSink()
    monitor = MonitorLoop(state, alert_sink=sink)
    monitor._check_image_pin_divergence("owner/repo", [r1, r2])

    assert len(sink.alerts) == 1, sink.alerts
    repo, check_class, name, got = sink.alerts[0]
    assert check_class == "image_pin_divergence"
    assert name == "?", "a repository fact must not be filed against a host"
    assert got is detail or got == detail
    assert repo == "owner/repo"


def test_check_image_pin_divergence_stays_quiet_when_the_host_reports_no_divergence(tmp_path):
    """The mirror case. Null means checked-and-agree OR could not check — both
    are "no divergence was observed", and neither is an alert to file."""
    state, runner = _image_state_state(tmp_path, "ghcr.io/o/r@sha256:" + "a" * 64)
    runner["image_pin_divergence"] = None
    state.registry.save()
    sink = _CollectSink()
    monitor = MonitorLoop(state, alert_sink=sink)
    monitor._check_image_pin_divergence("owner/repo", [runner])
    assert sink.alerts == [], sink.alerts


def test_check_image_pin_divergence_renders_the_host_string_without_matching_it(tmp_path):
    """Free text from an untrusted-as-input host: the detail is carried through
    as given (render, never match), the same policy as image_reason."""
    state, runner = _image_state_state(tmp_path, None, "podman not on PATH")
    hostile = "served x is y but the record is z —  <script>LOOK ME UP</script>"
    runner["image_pin_divergence"] = hostile
    state.registry.save()
    sink = _CollectSink()
    monitor = MonitorLoop(state, alert_sink=sink)
    monitor._check_image_pin_divergence("owner/repo", [runner])
    assert len(sink.alerts) == 1, sink.alerts
    assert sink.alerts[0][3] == hostile

