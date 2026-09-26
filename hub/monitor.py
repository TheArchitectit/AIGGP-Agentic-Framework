"""hub.monitor — GitHub API polling loop (D2a, D5).

The monitor combines two independent evidence channels:
  a) Hub-side GitHub API polling: runner status, queued-run age, check-run
     conclusions on watched branches, scheduled drift-scan recency.
  b) Spoke heartbeats: freshness of the last heartbeat per runner.

Either channel alone is sufficient to detect an offline runner or a stalled
queue (mon-channels-01). The poll loop runs in a daemon thread; it backs off
on 403/429 (rate limit) and logs loudly when GITHUB_TOKEN is absent so the
hub never passes vacuously.

The HTTP transport and its rate-limit handling live in hub/github_client.py;
this module is the polling POLICY — what to check, and what to alert on.

// spec: mon-channels-01, mon-online-01, mon-queue-01, mon-gates-01, mon-drift-01
// spec: secret-scan-07 — the hub-side rendering of the fleet sweep's state, via
// scan_view.scan_alerts (see hub/scan_view.py); this module only raises them.
// spec: coh-int-05 — the monitor is the FLEET ADAPTER for the coherence gate's
// CI conclusion; any non-passing conclusion must surface, never default-allow.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

from . import registry
from .alerts import AlertSink
from .config import Config
from .github_client import GitHubClient, parse_iso
from .scan_view import scan_alerts
from .server import HubState

log = logging.getLogger("hub.monitor")

# coh-int-05 (fleet half): the monitor TRANSPORTS the gate workflow's
# conclusion — an adapter does not compute one — so EVERY conclusion GitHub
# can attribute to a watched run except a pass must surface. Classifying only
# `failure` leaves timed_out/cancelled/action_required/neutral/stale to fall
# through to the recency window, where a FRESH such run reads healthy: the
# default-allow the requirement forbids. The membership is GitHub's documented
# run-conclusion enum minus `success` (a pass) and `skipped` — absent on
# purpose because coh-int-06 gives the skip its own class (its presence is
# pinned by tests/test_hub_monitor_default_deny.py, so deleting this line's
# contract cannot pass the suite).
NON_PASSING_CONCLUSIONS = frozenset(
    {"failure", "timed_out", "cancelled", "action_required", "neutral", "stale"})


class MonitorLoop:
    """Polls GitHub for runner/queue/gate/drift status per registered repo.

    Runs in a daemon thread. Each cycle:
      1. For each enrolled runner's repo:
         a. Check runner online status (mon-online-01)
         b. Check queued-run age (mon-queue-01)
         c. Check check-run conclusions on watched branches (mon-gates-01)
         d. Check drift-scan recency (mon-drift-01)
         e. Check spec-coherence presence/recency (coh-int-02, coh-int-07)
      2. Evaluate heartbeat freshness (mon-online-01, mon-channels-01)
      3. Raise alerts via AlertSink for any failures detected.

    Alerts are deduplicated by (repo, check-class, runner) — see Sprint 4.
    """

    def __init__(self, state: HubState, alert_sink: "AlertSink | None" = None) -> None:
        self.state = state
        self.config = state.config
        self.client = GitHubClient(
            api_base=self.config.github_api_base,
            token=os.environ.get("GITHUB_TOKEN", ""),
            backoff_max=self.config.api_backoff_max_sec,
        )
        self.alert_sink = alert_sink  # Sprint 4: AlertEngine with dedupe

    def run(self, stop_event) -> None:
        """Main poll loop. Blocks until stop_event is set."""
        log.info("monitor loop started (interval=%ds)", self.config.poll_interval_sec)
        while not stop_event.is_set():
            try:
                self.poll_cycle()
                # A completed cycle is the liveness signal /health reports.
                # Set after poll_cycle returns, so a wedged cycle stops
                # advancing it — that staleness is what a watchdog detects.
                self.state.note_poll()
            except Exception as e:  # noqa: BLE001 — monitor must never crash the hub
                log.error("poll cycle failed: %s", e, exc_info=True)
            # Sleep in small increments so stop_event is checked promptly.
            for _ in range(self.config.poll_interval_sec):
                if stop_event.is_set():
                    break
                time.sleep(1)
        log.info("monitor loop stopped")

    def poll_cycle(self) -> None:
        """One full monitoring cycle across all registered repos."""
        runners = self.state.registry.runners()
        # Group by repo to avoid redundant API calls.
        repos: dict[str, list[dict]] = {}
        for runner in runners:
            if not runner.get("enrolled"):
                continue
            repo = runner.get("repo", "")
            if repo:
                repos.setdefault(repo, []).append(runner)

        for repo, repo_runners in repos.items():
            try:
                self._poll_repo(repo, repo_runners)
            except Exception as e:  # noqa: BLE001
                log.error("poll failed for %s: %s", repo, e, exc_info=True)

    def _poll_repo(self, repo: str, runners: list[dict]) -> None:
        """Poll all checks for a single repo.

        The two checks that read ONLY the registry run FIRST, before any call
        that can raise out of this method. `github_client` catches HTTPError but
        not URLError, so a refused connection or a DNS failure propagates into
        poll_cycle's per-repo handler and aborts every check that has not run
        yet: ordering, not just independence, is what keeps an image deficiency
        or an unscanned repository from going quiet through a network outage.
        (Measured — placed last, a closed port silences both.)
        """
        owner = repo.split("/")[0]

        # --- 3.5 Evaluator-image readiness (img-cycle-03)
        self._check_image_readiness(repo, runners)

        # --- 3.6 Fleet scan state (secret-scan-07)
        self._check_scan_state(repo, runners)

        # --- 3.1 Runner status + queued-run age (mon-online-01, mon-queue-01)
        self._check_runner_status(repo, runners)
        self._check_queue_drain(repo, runners)

        # --- 3.2 Check-run conclusions on watched branches (mon-gates-01)
        self._check_gate_results(repo, owner)

        # --- 3.3 Drift-scan presence/recency (mon-drift-01)
        self._check_drift_scan(repo, owner)

        # --- 3.4 Spec-coherence presence/recency (coh-int-02, coh-int-07)
        self._check_spec_coherence(repo, owner)

    def _check_runner_status(self, repo: str, runners: list[dict]) -> None:
        """Check GitHub API runner status + heartbeat freshness (mon-online-01)."""
        owner = repo.split("/")[0]
        # Get the runner group for this repo.
        result = self.client.get_with_backoff(f"/repos/{repo}/actions/runners")
        if result is None:
            log.warning("could not fetch runners for %s (rate limited)", repo)
            return
        status, body = result
        if status != 200:
            log.warning("runner status fetch failed for %s: HTTP %d", repo, status)
            return

        api_runners = {r["name"]: r for r in body.get("runners", [])}
        stale_threshold_sec = self.config.heartbeat_interval_sec * 2
        now = datetime.now(timezone.utc)

        for runner in runners:
            name = runner["name"]
            api_runner = api_runners.get(name)

            # Check API status.
            api_online = api_runner is not None and api_runner.get("status") == "online"

            # Check heartbeat freshness.
            last_hb = parse_iso(runner.get("last_heartbeat"))
            hb_fresh = (
                last_hb is not None
                and (now - last_hb).total_seconds() < stale_threshold_sec
            )

            if not api_online or not hb_fresh:
                reasons = []
                if not api_online:
                    reasons.append("API status not online")
                if not hb_fresh:
                    age_str = f"{(now - last_hb).total_seconds() / 60:.1f}m" if last_hb else "never"
                    reasons.append(f"heartbeat stale ({age_str})")
                self._raise_alert(repo, "runner_offline", name,
                                  detail="; ".join(reasons))

    def _check_image_readiness(self, repo: str, runners: list[dict]) -> None:
        """A host that cannot serve the pinned image is not ready to gate.

        Deliberately NOT folded into `_check_runner_status`, which returns
        early when the runners API call fails: an image deficiency raised
        there would be silenced by a rate limit, precisely when an operator is
        looking at the dashboard. This check reads only the registry, so it
        cannot be starved by GitHub.

        The detail carries the reason the host gave, because "no image" alone
        does not say whether to fix the EnvironmentFile, install podman, or
        re-pull — and a host that reported NOTHING is told apart from one that
        reported a fault, in the sentence and not just in a trailing
        parenthetical: the two need different actions (provision the host, or
        fix what it reported), and a helper that predates the cycle is the
        first case on every already-enrolled host. img-cycle-03 keeps "unknown"
        and "cannot serve" separate for the same reason.
        """
        for runner in runners:
            if not registry.image_missing(runner):
                continue
            reason = runner.get("image_reason")
            if reason:
                detail = f"cannot serve the pinned evaluator image: {reason}"
            else:
                detail = ("cannot serve the pinned evaluator image: this host "
                          "has not reported an image state at all, so it cannot "
                          "be counted ready to gate")
            self._raise_alert(repo, "runner_image_missing", runner["name"], detail)

    def _check_scan_state(self, repo: str, runners: list[dict]) -> None:
        """A repository whose scan state is unknown is not a clean repository.

        secret-scan-07's hub half. Like `_check_image_readiness` above — and for
        the same reason — this reads only the registry, so a GitHub rate limit
        cannot silence it, and it is NOT folded into `_check_runner_status`,
        which returns early on an API failure.

        The sentences live in `scan_view.scan_alerts`: what a verdict should say
        is not a property of the poll loop, and this method exists to attach the
        repo and the runner name to whatever that view decides. It raises
        nothing of its own and re-renders nothing — a second opinion about
        whether a state is usable is exactly the divergence this repository
        keeps finding (the predicate is the single reader of that question).
        """
        for runner in runners:
            for check_class, detail in scan_alerts(runner):
                self._raise_alert(repo, check_class, runner["name"], detail)

    def _check_queue_drain(self, repo: str, runners: list[dict]) -> None:
        """Check for queued workflow runs older than threshold (mon-queue-01)."""
        owner = repo.split("/")[0]
        # Get recent workflow runs.
        result = self.client.get_with_backoff(
            f"/repos/{repo}/actions/runs?per_page=50&status=queued")
        if result is None:
            return
        status, body = result
        if status != 200:
            return

        threshold_sec = self.config.queue_threshold_min * 60
        now = datetime.now(timezone.utc)
        registered_labels = {lbl for r in runners for lbl in r.get("labels", [])}

        for run in body.get("workflow_runs", []):
            created = parse_iso(run.get("created_at"))
            if created is None:
                continue
            age_sec = (now - created).total_seconds()
            if age_sec < threshold_sec:
                continue

            # Check if this run targets a registered label.
            # The API doesn't expose labels directly on runs; we check the
            # run's runner group or just alert on any long-queued run for now.
            # (Refinement: match by run name or job labels in Sprint 4.)
            self._raise_alert(
                repo, "queue_stall", run.get("run_id", "?"),
                detail=f"queued {age_sec / 60:.0f}m (threshold {self.config.queue_threshold_min:.0f}m), "
                       f"run: {run.get('name', '?')}")

    def _check_gate_results(self, repo: str, owner: str) -> None:
        """Check latest check-run conclusions on watched branches (mon-gates-01)."""
        for branch in self.config.watched_branches:
            # Get the latest commit on the watched branch.
            result = self.client.get_with_backoff(f"/repos/{repo}/commits/{branch}?per_page=1")
            if result is None:
                continue
            status, body = result
            if status != 200:
                continue

            sha = body.get("sha", "")
            if not sha:
                continue

            # Get check runs for that commit.
            result = self.client.get_with_backoff(
                f"/repos/{repo}/commits/{sha}/check-runs?per_page=100")
            if result is None:
                continue
            status, body = result
            if status != 200:
                continue

            for check in body.get("check_runs", []):
                conclusion = check.get("conclusion")
                if conclusion in NON_PASSING_CONCLUSIONS:
                    self._raise_alert(
                        repo, "gate_failure", check.get("name", "?"),
                        detail=f"conclusion={conclusion}, branch={branch}, sha={sha[:8]}")

    def _check_drift_scan(self, repo: str, owner: str) -> None:
        """Check scheduled drift-scan presence/recency (mon-drift-01)."""
        # Find the drift-scan workflow by name pattern.
        match = self.config.drift_workflow_match
        result = self.client.get_with_backoff(f"/repos/{repo}/actions/workflows?per_page=100")
        if result is None:
            return
        status, body = result
        if status != 200:
            return

        drift_wf = None
        for wf in body.get("workflows", []):
            if match.lower() in wf.get("name", "").lower():
                drift_wf = wf
                break

        if drift_wf is None:
            # No drift-scan workflow found — alert (mon-drift-01: "no scan has completed").
            self._raise_alert(repo, "drift_overdue", "?",
                              detail=f"no workflow matching '{match}' found")
            return

        # Get the latest run of the drift-scan workflow.
        result = self.client.get_with_backoff(
            f"/repos/{repo}/actions/workflows/{drift_wf['id']}/runs?per_page=1")
        if result is None:
            return
        status, body = result
        if status != 200:
            return

        runs = body.get("workflow_runs", [])
        if not runs:
            self._raise_alert(repo, "drift_overdue", "?",
                              detail=f"no completed runs for workflow '{drift_wf['name']}'")
            return

        latest = runs[0]
        # Any non-passing conclusion alerts (coh-int-05 fleet half).
        if latest.get("conclusion") in NON_PASSING_CONCLUSIONS:
            self._raise_alert(
                repo, "drift_failed", "?",
                detail=f"latest drift scan did not pass "
                       f"(conclusion={latest.get('conclusion')}): "
                       f"{latest.get('html_url', '')}")
            return

        # Check recency: must have completed within one period + grace.
        completed_at = parse_iso(latest.get("completed_at"))
        if completed_at is None:
            self._raise_alert(repo, "drift_overdue", "?",
                              detail="latest drift scan has no completion timestamp")
            return

        # We don't know the exact schedule period from the API alone;
        # use a conservative default of 24h + grace (configurable).
        max_age_sec = 24 * 3600 + self.config.drift_grace_min * 60
        age_sec = (datetime.now(timezone.utc) - completed_at).total_seconds()
        if age_sec > max_age_sec:
            self._raise_alert(
                repo, "drift_overdue", "?",
                detail=f"last drift scan {age_sec / 3600:.1f}h ago (max {max_age_sec / 3600:.1f}h)")

    def _check_spec_coherence(self, repo: str, owner: str) -> None:
        """Check coherence-workflow presence/recency (coh-int-02, coh-int-07).

        The FIFTH check class (design.md round-9). Its own matcher, separate
        from drift's: the two workflows are different jobs in the same repo,
        and a repo with only one of them must be reported on the one it lacks,
        never quietly matched against the other.

        A MISSING coherence workflow is an alert, not silence (coh-pol-07).
        That is the point of the class — if deleting the workflow made the
        gate disappear quietly, the boundary would be removable by repository
        content, which is exactly what the requirement forbids. Presence of a
        workflow file is not enforcement; a missing one must not be invisible
        either.

        Scope is the configured `watched_branches` (coh-int-07): a green run on
        a branch nobody watches is not evidence for the watched branch. With no
        branch configured the check is an explicit no-op — not a pass, and not
        silence either, since an unconfigured repo is otherwise
        indistinguishable from a healthy one.
        """
        branches = [b for b in self.config.watched_branches if b != "default"]
        if not branches:
            self._raise_alert(
                repo, "coherence_unconfigured", "?",
                detail="no watched branches configured — the coherence check "
                       "is an explicit no-op, not a pass; set "
                       "HUB_WATCHED_BRANCHES to enable it")
            return

        match = self.config.coherence_workflow_match
        result = self.client.get_with_backoff(
            f"/repos/{repo}/actions/workflows?per_page=100")
        if result is None:
            return
        status, body = result
        if status != 200:
            return

        wf = None
        for candidate in body.get("workflows", []):
            if match.lower() in candidate.get("name", "").lower():
                wf = candidate
                break

        if wf is None:
            self._raise_alert(
                repo, "coherence_missing", "?",
                detail=f"no workflow matching '{match}' found — the coherence "
                       f"gate has been removed or renamed")
            return

        result = self.client.get_with_backoff(
            f"/repos/{repo}/actions/workflows/{wf['id']}/runs?per_page=100")
        if result is None:
            return
        status, body = result
        if status != 200:
            return

        latest = None
        for run in body.get("workflow_runs", []):
            if run.get("head_branch") in branches:
                latest = run
                break
        if latest is None:
            self._raise_alert(
                repo, "coherence_missing", "?",
                detail=f"no run of workflow '{wf['name']}' on any watched "
                       f"branch ({', '.join(branches)})")
            return

        if latest.get("conclusion") in NON_PASSING_CONCLUSIONS:
            # coh-int-05 fleet half: ANY non-passing conclusion is reported,
            # not just `failure` — a fresh timed_out/cancelled/… run must not
            # fall through to the recency window and read healthy.
            self._raise_alert(
                repo, "coherence_failure", "?",
                detail=f"latest coherence run did not pass "
                       f"(conclusion={latest.get('conclusion')}): "
                       f"{latest.get('html_url', '')}")
            return

        if latest.get("conclusion") == "skipped":
            # coh-int-06: a SKIPPED gate is not a pass. It is not a failure
            # either — the run explicitly declined to execute and said why —
            # so it gets its own class rather than being folded into
            # coherence_failure, which would misattribute a deliberate skip
            # to a broken gate.
            self._raise_alert(
                repo, "coherence_skipped", "?",
                detail=f"latest coherence run on branch "
                       f"{latest.get('head_branch')} reported SKIPPED: "
                       f"{latest.get('html_url', '')}")
            return

        # Recency, same 24h + grace window drift uses. The schedule period is
        # not visible from the API, so this is the same conservative default.
        completed_at = parse_iso(latest.get("completed_at"))
        if completed_at is None:
            self._raise_alert(
                repo, "coherence_overdue", "?",
                detail="latest coherence run has no completion timestamp")
            return
        max_age_sec = 24 * 3600 + self.config.drift_grace_min * 60
        age_sec = (datetime.now(timezone.utc) - completed_at).total_seconds()
        if age_sec > max_age_sec:
            self._raise_alert(
                repo, "coherence_overdue", "?",
                detail=f"last coherence run {age_sec / 3600:.1f}h ago "
                       f"(max {max_age_sec / 3600:.1f}h)")

    def _raise_alert(self, repo: str, check_class: str, runner: str, detail: str) -> None:
        """Raise an alert. Sprint 4 adds dedupe + GitHub issue filing."""
        if self.alert_sink is not None:
            self.alert_sink.raise_alert(repo=repo, check_class=check_class,
                                        runner=runner, detail=detail)
        else:
            # No alert sink configured (Sprint 3 stub): log loudly.
            log.warning("ALERT [%s/%s/%s] %s", repo, check_class, runner, detail)



