# // spec: coh-int-05
"""coh-int-05 fleet half: the hub's monitor is an ADAPTER — it transports the
gate workflow's CI conclusion, and an adapter that cannot obtain a parseable
canonical result MUST surface ERROR semantics, never a default-allow.

The container driver's half of this requirement is already pinned (timeout /
unparseable result / missing bundle -> ERROR/32) in
tests/test_hub_coherence_container.py. This file pins the hub's: a run of the
watched gate workflow that concluded ANYTHING other than a pass or the
explicit SKIPPED contract must alert. Reading `== "failure"` only, the other
non-passing conclusions fall through to the recency window and — a FRESH run,
inside the window — produce no alert at all: the gate's absence reads healthy,
which is exactly the neutral outcome coh-int-05 forbids. Reachable by ordinary
operation: the coherence template declares `timeout-minutes: 20`, so a slow
evaluation ends as `timed_out`, not `failure`.

Anti-vacuity rule this file obeys: the conclusion lists are written HERE, in
the tests, never imported from the production constant — a test iterating the
constant it is supposed to pin shrinks in silence when a member is deleted.

Dual-runnable: pytest collects test_*; `python3
tests/test_hub_monitor_default_deny.py` runs them too.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.config import Config  # noqa: E402
from hub.monitor import MonitorLoop  # noqa: E402
from hub.server import HubState  # noqa: E402

from tests.test_hub_monitor import _iso, _start_fake_gh  # noqa: E402

# GitHub Actions workflow-run conclusions that are not passes and not the
# contract's explicit SKIPPED. `success` excluded by definition; `skipped`
# excluded because coh-int-06 gives it its own alert class (pinned elsewhere).
# in_progress/queued/requested/waiting/pending are NOT here: the API carries
# those in the `status` field, never in `conclusion`, and a run with a fresh
# completion timestamp (which the tests fabricate) can only be terminal.
NON_PASSING = ("failure", "timed_out", "cancelled", "action_required",
               "neutral", "stale")

# The literals that must already have worked before this slice (regression
# guard on top of the new coverage — dropping it here would let the fix
# silently narrow the old contract).
ALREADY_PINNED = {"coherence": "failure", "drift": "failure",
                  "gates": ("failure", "timed_out")}


def _monitor(tmp_path, routes):
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    config.watched_branches = ["main"]
    config.drift_grace_min = 10.0
    state = HubState(config)
    alerts = []

    class CollectSink:
        def raise_alert(self, repo, check_class, runner, detail):
            alerts.append((repo, check_class, runner, detail))

    server, port = _start_fake_gh(routes)
    monitor = MonitorLoop(state, alert_sink=CollectSink())
    monitor.client.api_base = f"http://127.0.0.1:{port}"
    return server, monitor, alerts


def _coherence_classes(tmp_path, conclusion):
    now = datetime.now(timezone.utc)
    server, monitor, alerts = _monitor(tmp_path, {
        "/repos/owner/repo/actions/workflows?per_page=100": lambda: (200, {
            "workflows": [{"id": 42, "name": "Coherence Scan"}]}),
        "/repos/owner/repo/actions/workflows/42/runs?per_page=100": lambda: (200, {
            "workflow_runs": [
                {"conclusion": conclusion, "head_branch": "main",
                 "completed_at": _iso(now),
                 "html_url": "https://example.invalid/run/9"}]}),
    })
    try:
        monitor._check_spec_coherence("owner/repo", "owner")
        return {a[1] for a in alerts}
    finally:
        server.shutdown()


def _drift_classes(tmp_path, conclusion):
    now = datetime.now(timezone.utc)
    server, monitor, alerts = _monitor(tmp_path, {
        "/repos/owner/repo/actions/workflows?per_page=100": lambda: (200, {
            "workflows": [{"id": 99, "name": "drift-scan"}]}),
        "/repos/owner/repo/actions/workflows/99/runs?per_page=1": lambda: (200, {
            "workflow_runs": [{"conclusion": conclusion,
                               "completed_at": _iso(now)}]}),
    })
    try:
        monitor._check_drift_scan("owner/repo", "owner")
        return {a[1] for a in alerts}
    finally:
        server.shutdown()


def _gates_classes(tmp_path, conclusion):
    server, monitor, alerts = _monitor(tmp_path, {
        "/repos/owner/repo/commits/main?per_page=1": lambda: (200, {"sha": "abc1234"}),
        "/repos/owner/repo/commits/abc1234/check-runs?per_page=100": lambda: (200, {
            "check_runs": [{"name": "gate", "conclusion": conclusion}]}),
    })
    try:
        monitor._check_gate_results("owner/repo", "owner")
        return {a[1] for a in alerts}
    finally:
        server.shutdown()


def test_coherence_fresh_nonpassing_conclusion_alerts_never_reads_healthy(tmp_path):
    """coh-int-05, coherence check: EVERY non-passing conclusion alerts on a
    fresh run. Before this pin only `failure` and `skipped` classified; a
    timed_out/cancelled/action_required/neutral/stale run inside the recency
    window produced zero alerts — adapter default-allow."""
    for c in NON_PASSING:
        classes = _coherence_classes(tmp_path, c)
        assert classes, \
            f"a fresh coherence run concluding {c!r} alerted nothing — " \
            "non-passing must never read healthy (coh-int-05)"
        if c == "failure":
            assert "coherence_failure" in classes, \
                f"the pre-existing class for {c!r} drifted: {classes}"
        elif c == "skipped":
            assert "coherence_skipped" in classes
        else:
            # Named or folded into an existing non-pass class — but the class
            # must NOT be one that means "passed with a note": it must not
            # collide with the healthy path's silence.
            assert "coherence_failure" in classes or \
                any(k.startswith("coherence") for k in classes), \
                f"{c!r} alerted an unrelated class set: {classes}"


def test_drift_fresh_nonpassing_conclusion_alerts_never_reads_healthy(tmp_path):
    """coh-int-05, drift check: same membership law for the drift workflow.
    Only `failure` classified; `timed_out` — the scheduled scan's most likely
    real-world non-pass — fell through."""
    for c in NON_PASSING:
        classes = _drift_classes(tmp_path, c)
        assert classes, \
            f"a fresh drift scan concluding {c!r} alerted nothing (coh-int-05)"
        if c == ALREADY_PINNED["drift"]:
            assert "drift_failed" in classes, \
                f"the pre-existing drift_failed class drifted: {classes}"


def test_gates_nonpassing_check_run_conclusion_alerts(tmp_path):
    """coh-int-05, check-run gate results: the monitor already covered
    failure+timed_out but not cancelled/action_required/neutral — a check-run
    cancelled by a newer push on a watched branch read neutral-silent."""
    for c in NON_PASSING:
        classes = _gates_classes(tmp_path, c)
        assert classes, \
            f"a check-run concluding {c!r} alerted nothing (coh-int-05)"
        if c in ALREADY_PINNED["gates"]:
            assert "gate_failure" in classes, \
                f"the pre-existing gate_failure class drifted for {c!r}: {classes}"


def test_success_stays_silent_in_all_three_checks(tmp_path):
    """The default-deny law has a floor: a PASS must not alert, or the fix is
    just alert-noise. The non-vacuity counterpart of the loops above."""
    assert _coherence_classes(tmp_path, "success") == set()
    assert _drift_classes(tmp_path, "success") == set()
    assert _gates_classes(tmp_path, "success") == set()


def test_skipped_keeps_its_own_coherence_class(tmp_path):
    """coh-int-06's contract survives the widening: SKIPPED must NOT be
    folded into the failure class by the new membership test — the list in
    test 1 excludes it, and production must keep the separate branch."""
    classes = _coherence_classes(tmp_path, "skipped")
    assert "coherence_skipped" in classes, f"skip class regressed: {classes}"
    assert "coherence_failure" not in classes, \
        f"a deliberate skip is not a failed gate: {classes}"


def main() -> int:
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))


if __name__ == "__main__":
    main()
