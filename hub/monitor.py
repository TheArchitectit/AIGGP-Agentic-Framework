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
// spec: coh-int-07, coh-int-02 — _check_spec_coherence polls EACH registered
// repo against that repo's watched branches (never borrowing another repo's
// result); no watched branches is the explicit coherence_unconfigured no-op.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

from . import registry
from .alerts import AlertSink
from . import coherence_view
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

# The transport (`GitHubClient`, `parse_iso`) arrives from hub/github_client.py,
# which exists because this file reached the 500-line limit regression_sizes.py
# enforces. A second copy was briefly inlined here, shadowing the import: the
# class the tests pinned was not the class the monitor ran.


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
        token_file = os.path.join(self.config.data_dir, "github_token.txt")
        self.client = GitHubClient(
            api_base=self.config.github_api_base,
            token=os.environ.get("GITHUB_TOKEN", ""),
            token_file=token_file,
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
        # Refresh token from file so rotations (revoke/re-enroll) take effect.
        self.client.refresh_token()
        # A locked deep copy: HTTP threads mutate these dicts in place
        # (heartbeat writes digest/reason/scan_state as separate assignments),
        # and the readiness checks below read fields across those writes.
        runners = self.state.runners_snapshot()
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
        # --- 3.5 image readiness (img-cycle-03)
        self._check_image_readiness(repo, runners)

        # --- 3.5b served-vs-record (img-cycle-05)
        self._check_image_pin_divergence(repo, runners)

        # --- 3.6 Fleet scan state (secret-scan-07)
        self._check_scan_state(repo, runners)
        # --- 3.1 runner status + queued-run age (mon-online-01, mon-queue-01)
        self._check_runner_status(repo, runners)
        self._check_queue_drain(repo, runners)
        # --- 3.2 gate conclusions (mon-gates-01), 3.3 drift (mon-drift-01),
        # --- 3.4 spec coherence (coh-int-02, coh-int-07)
        self._check_gate_results(repo, owner)
        self._check_drift_scan(repo, owner)
        self._check_spec_coherence(repo, owner)

    def _default_branch(self, repo: str) -> str | None:
        """Resolve the repo's actual default branch (F6). The config sentinel
        'default' is NOT a branch name — the old literal 404'd the gate-results
        check on every default deployment, silently disabling a whole check
        class."""
        result = self.client.get_with_backoff(f"/repos/{repo}")
        if result is None:
            return None
        status, body = result
        if status != 200 or not isinstance(body, dict):
            log.warning("could not resolve default branch for %s: HTTP %d",
                        repo, status)
            return None
        branch = body.get("default_branch")
        return branch if isinstance(branch, str) and branch else None

    def _watched_branches(self, repo: str) -> list[str]:
        out: list[str] = []
        for branch in self.config.watched_branches:
            if branch == "default":
                resolved = self._default_branch(repo)
                if resolved is None:
                    log.warning(
                        "watched branch 'default' could not be resolved for %s "
                        "this cycle — gate-results check skipped (not clean)",
                        repo)
                    continue
                out.append(resolved)
            else:
                out.append(branch)
        return out

    def _check_runner_status(self, repo: str, runners: list[dict]) -> None:
        """Check GitHub API runner status + heartbeat freshness (mon-online-01)."""
        owner = repo.split("/")[0]
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

            # Check API status. Distinguish "not found" from "found but offline".
            if api_runner is None:
                self._raise_alert(repo, "runner_missing", name,
                                  detail="runner not found in GitHub API for this repo — "
                                         "may be unregistered or assigned to a different repo")
                continue
            api_online = api_runner.get("status") == "online"

            # Check heartbeat freshness.
            last_hb = parse_iso(runner.get("last_heartbeat"))
            hb_fresh = (
                last_hb is not None
                and (now - last_hb).total_seconds() < stale_threshold_sec
            )

            if not api_online or not hb_fresh:
                reasons = []
                if not api_online:
                    reasons.append(f"API status={api_runner.get('status', 'unknown')}")
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

    def _check_image_pin_divergence(self, repo: str, runners: list[dict]) -> None:
        """Served-vs-recorded is a fact about the repository (img-cycle-05, D6).

        Raised ONCE per repo under runner "?", not once per host: every host
        that can reach the registry reports the same divergence, and filing one
        issue per host turns one re-pin decision into N copies of the same
        ticket. The detail is the host-reported string, rendered never matched
        (same policy as image_reason) — it already names both digests, which is
        what the requirement asks the alert to name.

        Reads only the registry, so a GitHub rate limit cannot silence it — same
        placement as `_check_image_readiness` above.
        """
        for runner in runners:
            detail = runner.get("image_pin_divergence")
            if isinstance(detail, str) and detail:
                self._raise_alert(repo, "image_pin_divergence", "?", detail)
                return

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
            # The runs API field is `id`, not `run_id`: the wrong key made
            # every queue-stall alert runner="?" so all stalls deduped into
            # one issue and the cooldown then hid distinct stalls for an hour.
            self._raise_alert(
                repo, "queue_stall", str(run.get("id", "?")),
                detail=f"queued {age_sec / 60:.0f}m (threshold {self.config.queue_threshold_min:.0f}m), "
                       f"run: {run.get('name', '?')}")

    def _check_gate_results(self, repo: str, owner: str = "") -> None:
        """Check latest check-run conclusions on watched branches (mon-gates-01)."""
        for branch in self._watched_branches(repo):
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

    def _check_drift_scan(self, repo: str, owner: str = "") -> None:
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

    def _check_spec_coherence(self, repo: str, owner: str = "") -> None:
        """Check the coherence gate on two independent channels (union).

        Channel A — workflow runs (coh-int-02/05/06/07). Channel B —
        check-runs on watched branches (S6). Neither substitutes for the
        other; the shared implementation lives in hub/coherence_view.py.
        """
        coherence_view.check_workflow_runs(
            repo, self.config, self.client, self._raise_alert, parse_iso,
            NON_PASSING_CONCLUSIONS)
        coherence_view.check_check_runs(
            repo, self.config, self.client, self._raise_alert,
            self._watched_branches, NON_PASSING_CONCLUSIONS)

    def _raise_alert(self, repo: str, check_class: str, runner: str, detail: str) -> None:
        """Raise an alert. Sprint 4 adds dedupe + GitHub issue filing."""
        if self.alert_sink is not None:
            self.alert_sink.raise_alert(repo=repo, check_class=check_class,
                                        runner=runner, detail=detail)
        else:
            # No alert sink configured (Sprint 3 stub): log loudly.
            log.warning("ALERT [%s/%s/%s] %s", repo, check_class, runner, detail)
