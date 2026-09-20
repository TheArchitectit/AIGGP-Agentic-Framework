"""Tests for the spec-coherence monitor check class (coh-int-02, coh-int-07).

Split from test_hub_monitor.py along the capability seam: that suite covers the
four pre-existing check classes (runner/queue/gate/drift), this one covers the
fifth, added for the coherence service. Sharing the fake-GitHub-server harness
keeps the split mechanical rather than a copy.

The load-bearing property here is coh-pol-07's: a MISSING coherence workflow
must alert, never go quiet. If deleting the workflow silenced the gate, the
boundary would be removable by repository content.

Dual-runnable: pytest collects test_*; `python3 tests/test_hub_spec_coherence.py`
runs them too.
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
from hub.monitor import MonitorLoop  # noqa: E402
from hub.server import HubState  # noqa: E402

# Reuse the fake-server harness from the sibling suite rather than copying it.
from tests.test_hub_monitor import _iso, _start_fake_gh  # noqa: E402


def test_coherence_workflow_match_default_and_env_override():
    """coh-int-07: coherence has its own matcher, independent of drift's.

    The drift matcher must stay untouched — a repo whose drift workflow is
    named "Drift Scan" and whose coherence workflow is named "Coherence Scan"
    has to be matchable by both, with neither shadowing the other.
    """
    assert Config().coherence_workflow_match == "coherence"
    old = os.environ.get("HUB_COHERENCE_WORKFLOW_MATCH")
    try:
        os.environ["HUB_COHERENCE_WORKFLOW_MATCH"] = "spec-coherence"
        cfg = Config.from_env()
        assert cfg.coherence_workflow_match == "spec-coherence"
        # The drift knob is a SEPARATE field and must not have moved.
        assert cfg.drift_workflow_match == "drift"
    finally:
        if old is None:
            os.environ.pop("HUB_COHERENCE_WORKFLOW_MATCH", None)
        else:
            os.environ["HUB_COHERENCE_WORKFLOW_MATCH"] = old


def test_check_spec_coherence_alerts_on_failed_run(tmp_path):
    """A failed coherence run raises coherence_failure (coh-int-02/07)."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.watched_branches = ["main"]
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner, detail))

    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/workflows?per_page=100": lambda: (200, {
            "workflows": [{"id": 42, "name": "Coherence Scan"}]}),
        "/repos/owner/repo/actions/workflows/42/runs?per_page=100": lambda: (200, {
            "workflow_runs": [
                {"conclusion": "failure", "head_branch": "main",
                 "completed_at": _iso(datetime.now(timezone.utc)),
                 "html_url": "https://example.invalid/run/1"}
            ]}),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_spec_coherence("owner/repo", "owner")
        assert any(a[1] == "coherence_failure" for a in alerts), \
            f"expected coherence_failure, got {alerts}"
    finally:
        server.shutdown()


def test_check_spec_coherence_no_workflow_found(tmp_path):
    """coh-pol-07's workflow-deleted scenario: a MISSING coherence workflow
    is an alert, never silence.

    This is the whole point of the check class. If deleting the workflow made
    the gate disappear quietly, the boundary would be removable by repository
    content — the exact thing coh-pol-07 forbids.
    """
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.watched_branches = ["main"]
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner, detail))

    server, port = _start_fake_gh({
        # A drift workflow exists, but no coherence workflow does.
        "/repos/owner/repo/actions/workflows?per_page=100": lambda: (200, {
            "workflows": [{"id": 1, "name": "Drift Scan"}]}),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_spec_coherence("owner/repo", "owner")
        assert any(a[1] == "coherence_missing" for a in alerts), \
            f"expected coherence_missing, got {alerts}"
    finally:
        server.shutdown()


def test_check_spec_coherence_healthy_run_does_not_alert(tmp_path):
    """Control: a recent successful coherence run is silent.

    Without this, an alert-everything implementation would pass both tests
    above while being useless.
    """
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.watched_branches = ["main"]
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner, detail))

    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/workflows?per_page=100": lambda: (200, {
            "workflows": [{"id": 42, "name": "Coherence Scan"}]}),
        "/repos/owner/repo/actions/workflows/42/runs?per_page=100": lambda: (200, {
            "workflow_runs": [
                {"conclusion": "success", "head_branch": "main",
                 "completed_at": _iso(datetime.now(timezone.utc))}
            ]}),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_spec_coherence("owner/repo", "owner")
        assert not alerts, f"unexpected alerts: {alerts}"
    finally:
        server.shutdown()


def test_check_spec_coherence_does_not_match_the_drift_workflow(tmp_path):
    """The two matchers must not shadow each other (coh-int-07).

    A repo with only a drift workflow has NO coherence workflow; the coherence
    check must report that missing, not silently adopt the drift workflow's
    run as its own evidence.
    """
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.drift_workflow_match = "drift"
    config.coherence_workflow_match = "coherence"
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner, detail))

    # The drift workflow is named so a SHARED matcher would match it, and it
    # is FAILING. If coherence borrowed drift's matcher, the failure would be
    # reported as coherence_failure. Only its own matcher's verdict is asserted
    # here — whether a missing workflow alerts at all is
    # test_check_spec_coherence_no_workflow_found's claim, not this one's.
    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/workflows?per_page=100": lambda: (200, {
            "workflows": [{"id": 1, "name": "Drift Scan"}]}),
        "/repos/owner/repo/actions/workflows/1/runs?per_page=1": lambda: (200, {
            "workflow_runs": [
                {"conclusion": "failure", "head_branch": "main",
                 "completed_at": _iso(datetime.now(timezone.utc))}
            ]}),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_spec_coherence("owner/repo", "owner")
        classes = {a[1] for a in alerts}
        assert "coherence_failure" not in classes, \
            f"drift workflow was adopted as coherence evidence: {alerts}"
    finally:
        server.shutdown()


def test_check_spec_coherence_ignores_runs_on_unwatched_branches(tmp_path):
    """coh-int-07 watched-branch scope: only configured branches are evidence.

    A green coherence run on a branch nobody watches must NOT stand in for the
    watched branch's absent one. Reporting healthy because some other branch
    passed is the "borrowing another result" failure coh-int-07 forbids, moved
    from repos to branches.
    """
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.watched_branches = ["main"]
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner, detail))

    now = datetime.now(timezone.utc)
    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/workflows?per_page=100": lambda: (200, {
            "workflows": [{"id": 42, "name": "Coherence Scan"}]}),
        "/repos/owner/repo/actions/workflows/42/runs?per_page=100": lambda: (200, {
            "workflow_runs": [
                {"conclusion": "success", "head_branch": "feature/x",
                 "completed_at": _iso(now)},
            ]}),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_spec_coherence("owner/repo", "owner")
        classes = {a[1] for a in alerts}
        assert "coherence_missing" in classes, \
            f"unwatched-branch run was adopted as the watched branch's " \
            f"evidence: {alerts}"
    finally:
        server.shutdown()


def test_check_spec_coherence_accepts_a_run_on_a_watched_branch(tmp_path):
    """Control for the branch filter: a run ON the watched branch is evidence.

    Without this, a filter that rejected everything would pass the test above
    while making the check permanently red — and every real repo red.
    """
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.watched_branches = ["main"]
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner, detail))

    now = datetime.now(timezone.utc)
    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/workflows?per_page=100": lambda: (200, {
            "workflows": [{"id": 42, "name": "Coherence Scan"}]}),
        "/repos/owner/repo/actions/workflows/42/runs?per_page=100": lambda: (200, {
            "workflow_runs": [
                {"conclusion": "success", "head_branch": "feature/x",
                 "completed_at": _iso(now)},
                {"conclusion": "success", "head_branch": "main",
                 "completed_at": _iso(now)},
            ]}),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_spec_coherence("owner/repo", "owner")
        assert not alerts, f"a healthy watched-branch run must be silent: {alerts}"
    finally:
        server.shutdown()


def _skipped_run_alerts(tmp_path, *, age_hours=0.0):
    """Run the check against a repo whose latest watched-branch run skipped.

    `age_hours` backdates the completion timestamp. Fresh (the default) a skip
    cannot breach the recency window, so `coherence_overdue` is unreachable and
    its absence proves nothing about ordering — it only shows the class is not
    *named*. Backdated past the window, the same skip WOULD breach it, so
    falling through the skip branch would report staleness. That is the
    reachable state the ordering claim needs.
    """
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.watched_branches = ["main"]
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner, detail))

    now = datetime.now(timezone.utc) - timedelta(hours=age_hours)
    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/workflows?per_page=100": lambda: (200, {
            "workflows": [{"id": 42, "name": "Coherence Scan"}]}),
        "/repos/owner/repo/actions/workflows/42/runs?per_page=100": lambda: (200, {
            "workflow_runs": [
                {"conclusion": "skipped", "head_branch": "main",
                 "completed_at": _iso(now),
                 "html_url": "https://example.invalid/run/9"},
            ]}),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_spec_coherence("owner/repo", "owner")
        return {a[1] for a in alerts}
    finally:
        server.shutdown()


def test_check_spec_coherence_skipped_run_is_never_silent(tmp_path):
    """coh-int-06: a SKIPPED gate raises SOMETHING — it is never absence-as-pass.

    The hub-side half of the requirement, and the case most likely to be read
    as green: the workflow concluded successfully, the check class sees a
    completed run on the watched branch, and nothing failed. Silence here
    would make "the gate did not run" indistinguishable from "the gate
    passed", which is the failure coh-int-06 exists to name.

    This test claims only that the skip is not silent. WHICH class it carries
    is the next test's claim — asserting the class here as well would leave
    that test unpinned, since it would already have failed on this line.
    """
    assert _skipped_run_alerts(tmp_path), \
        "a SKIPPED gate must be reported, never read as pass"


def test_skipped_run_carries_its_own_class(tmp_path):
    """coh-int-06: the skip is named as a SKIPPED, not folded into another class.

    "Non-passing" and "failed" are different states with different owners — a
    repo whose runner cannot host the pinned image needs its runtime fixed, one
    with a red gate needs its candidate fixed. Reporting the skip under any
    other non-passing class would lose that distinction while still looking
    alert. Both exclusions are asserted here because they are one claim seen
    from two sides: that nothing else was reported INSTEAD of the skip. Split
    across two tests, either one alone would be pinned by the other's failure.
    """
    classes = _skipped_run_alerts(tmp_path)
    assert "coherence_skipped" in classes, \
        "a SKIPPED gate must be reported as a SKIPPED"
    assert "coherence_failure" not in classes, \
        f"a deliberate skip is not a broken gate: {classes}"


def test_check_spec_coherence_alerts_on_overdue_run(tmp_path):
    """The recency window is real: a stale watched-branch run alerts.

    Without this, the `coherence_overdue` raise can be deleted with the suite
    still green — found by mutation, not by reading. A gate that stopped
    firing would then go unreported, which is the same silent-gate failure
    coh-pol-07 forbids, arriving through the schedule instead of the file.
    """
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.watched_branches = ["main"]
    config.drift_grace_min = 10.0
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner, detail))

    # 30h ago: past the 24h + 10min window.
    old = datetime.now(timezone.utc) - timedelta(hours=30)
    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/workflows?per_page=100": lambda: (200, {
            "workflows": [{"id": 42, "name": "Coherence Scan"}]}),
        "/repos/owner/repo/actions/workflows/42/runs?per_page=100": lambda: (200, {
            "workflow_runs": [
                {"conclusion": "success", "head_branch": "main",
                 "completed_at": _iso(old)},
            ]}),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_spec_coherence("owner/repo", "owner")
        assert any(a[1] == "coherence_overdue" for a in alerts), \
            f"expected coherence_overdue, got {alerts}"
    finally:
        server.shutdown()


def test_check_spec_coherence_skipped_run_is_not_reported_as_staleness(tmp_path):
    """A skip is reported on its own terms, not as a missed schedule.

    The run is backdated 30h — past the 24h + 10min window — so an
    implementation that let the skip fall through to the recency check WOULD
    report staleness here. That is the whole point of the backdating: against a
    fresh skip the assertion passes whether or not the ordering is right, and a
    test that cannot fail is not a pin. The skip has to be diverted BEFORE the
    recency branch, which is a different line from the one that names its
    class.
    """
    classes = _skipped_run_alerts(tmp_path, age_hours=30)
    assert "coherence_skipped" in classes, \
        f"expected the skip to be reported: {classes}"
    assert "coherence_overdue" not in classes, \
        f"a skip is not staleness: {classes}"


def test_check_spec_coherence_no_watched_branches_alerts_unconfigured(tmp_path):
    """coh-int-07 watched-branch scenario: no configured branches is a no-op
    that is NOT a pass — and the user's decision is that it is not silence
    either.

    The spec reads "records an explicit no-op (not a pass) where none are
    configured". An unconfigured repo and a healthy one are indistinguishable
    from the outside if the no-op is silent, so the no-op is surfaced through
    the ordinary AlertSink. It must also NOT be reported as the gate being
    missing: nothing was removed here, the hub was never told what to watch.
    """
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.watched_branches = []
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner, detail))

    called = {"n": 0}

    class CountingHandler:
        pass

    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/workflows?per_page=100": lambda: (
            called.__setitem__("n", called["n"] + 1) or (200, {"workflows": []})),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor._check_spec_coherence("owner/repo", "owner")
        classes = {a[1] for a in alerts}
        assert "coherence_unconfigured" in classes, \
            f"expected coherence_unconfigured, got {alerts}"
        assert "coherence_missing" not in classes, \
            f"an unconfigured repo must not be reported as a removed gate: {alerts}"
        assert called["n"] == 0, \
            "no API call is meaningful when no branch is watched"
    finally:
        server.shutdown()


def test_poll_repo_runs_the_coherence_check(tmp_path):
    """The check is WIRED, not merely implemented (coh-int-02).

    A check class that exists but is never called from _poll_repo is dead
    configuration — the Cycle A m8 defect class. Pinned by observing the
    alert through the real poll path.
    """
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.watched_branches = ["main"]
    state = HubState(config)

    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner, detail))

    now = datetime.now(timezone.utc)
    server, port = _start_fake_gh({
        "/repos/owner/repo/actions/runners": lambda: (200, {"runners": [
            {"name": "r1", "status": "online"}]}),
        "/repos/owner/repo/actions/runs?per_page=50&status=queued": lambda: (
            200, {"workflow_runs": []}),
        "/repos/owner/repo/commits/main?per_page=1": lambda: (
            200, {"sha": "abc1234", "commit": {"sha": "abc1234"}}),
        "/repos/owner/repo/commits/abc1234/check-runs?per_page=100": lambda: (
            200, {"check_runs": []}),
        "/repos/owner/repo/actions/workflows?per_page=100": lambda: (200, {
            "workflows": [{"id": 42, "name": "Coherence Scan"}]}),
        "/repos/owner/repo/actions/workflows/42/runs?per_page=100": lambda: (200, {
            "workflow_runs": [
                {"conclusion": "failure", "head_branch": "main",
                 "completed_at": _iso(now),
                 "html_url": "https://example.invalid/run/1"}
            ]}),
    })
    try:
        monitor = MonitorLoop(state, alert_sink=CollectSink())
        monitor.client.api_base = f"http://127.0.0.1:{port}"
        monitor.config.watched_branches = ["main"]
        monitor.config.queue_threshold_min = 30.0
        monitor._poll_repo("owner/repo", [
            {"name": "r1", "repo": "owner/repo", "labels": ["devgate"],
             "last_heartbeat": _iso(now)}])
        assert any(a[1] == "coherence_failure" for a in alerts), \
            f"coherence check did not run in _poll_repo: {alerts}"
    finally:
        server.shutdown()


def main() -> int:
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))


if __name__ == "__main__":
    main()
