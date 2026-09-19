"""hub.monitor — GitHub API polling loop (D2a, D5).

The monitor combines two independent evidence channels:
  a) Hub-side GitHub API polling: runner status, queued-run age, check-run
     conclusions on watched branches, scheduled drift-scan recency.
  b) Spoke heartbeats: freshness of the last heartbeat per runner.

Either channel alone is sufficient to detect an offline runner or a stalled
queue (mon-channels-01). The poll loop runs in a daemon thread; it backs off
on 403/429 (rate limit) and logs loudly when GITHUB_TOKEN is absent so the
hub never passes vacuously.

Stdlib-only: urllib.request for GitHub API calls, no pip dependencies.

// spec: mon-channels-01, mon-online-01, mon-queue-01, mon-gates-01, mon-drift-01
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from .alerts import AlertSink
from .config import Config
from .server import HubState

log = logging.getLogger("hub.monitor")


def _parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp; return None on failure."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class GitHubClient:
    """Minimal GitHub REST client (stdlib urllib). Backs off on 403/429."""

    def __init__(self, api_base: str, token: str, backoff_max: int = 120) -> None:
        self.api_base = api_base.rstrip("/")
        self.token = token
        self.backoff_max = backoff_max
        self._last_request_time = 0.0
        # Retry-After from the most recent 403/429 (F7): GitHub sends it as an
        # HTTP HEADER; the old code looked for body keys that never exist, so
        # backoff always fell through to the exponential default.
        self._last_retry_after: int | None = None

    def _request(self, method: str, path: str, body: dict | None = None,
                 accept: str = "application/vnd.github+json") -> tuple[int, dict | list]:
        """Make an authenticated GitHub API request. Returns (status, parsed_body)."""
        url = f"{self.api_base}{path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode()
                return resp.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                header = e.headers.get("Retry-After") if e.headers else None
                try:
                    self._last_retry_after = int(header) if header else None
                except (TypeError, ValueError):
                    self._last_retry_after = None
            body_raw = e.read().decode() if e.fp else ""
            try:
                parsed = json.loads(body_raw) if body_raw else {}
            except json.JSONDecodeError:
                parsed = {"message": body_raw[:200]}
            return e.code, parsed

    def get(self, path: str) -> tuple[int, dict | list]:
        return self._request("GET", path)

    def post(self, path: str, body: dict) -> tuple[int, dict | list]:
        return self._request("POST", path, body=body)

    def get_with_backoff(self, path: str, max_retries: int = 3) -> tuple[int, dict | list] | None:
        """GET with backoff on 403/429. Returns None if all retries exhausted."""
        for attempt in range(max_retries):
            status, body = self.get(path)
            if status == 200:
                return (status, body)
            if status in (403, 429):
                # Honor the actual Retry-After header when GitHub sent one
                # (F7); otherwise exponential backoff, capped.
                retry_after = self._last_retry_after
                self._last_retry_after = None
                wait = min(retry_after if retry_after else (2 ** attempt) * 10,
                           self.backoff_max)
                log.warning("rate limited on %s (attempt %d/%d), backing off %ds",
                            path, attempt + 1, max_retries, wait)
                time.sleep(wait)
                continue
            # Other errors: return immediately.
            return (status, body)
        return None


class MonitorLoop:
    """Polls GitHub for runner/queue/gate/drift status per registered repo.

    Runs in a daemon thread. Each cycle:
      1. For each enrolled runner's repo:
         a. Check runner online status (mon-online-01)
         b. Check queued-run age (mon-queue-01)
         c. Check check-run conclusions on watched branches (mon-gates-01)
         d. Check drift-scan recency (mon-drift-01)
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
        # Snapshot under the hub's registry lock (F10): iterating the live
        # list while an HTTP thread saves can observe torn state.
        runners = self.state.snapshot_runners()
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
        """Poll all checks for a single repo."""
        # --- 3.1 Runner status + queued-run age (mon-online-01, mon-queue-01)
        self._check_runner_status(repo, runners)
        self._check_queue_drain(repo, runners)

        # --- 3.2 Check-run conclusions on watched branches (mon-gates-01)
        self._check_gate_results(repo)

        # --- 3.3 Drift-scan presence/recency (mon-drift-01)
        self._check_drift_scan(repo)

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
            last_hb = _parse_iso(runner.get("last_heartbeat"))
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
            created = _parse_iso(run.get("created_at"))
            if created is None:
                continue
            age_sec = (now - created).total_seconds()
            if age_sec < threshold_sec:
                continue

            # F5: the run identifier field is `id` — the old `run_id` key
            # never exists, so every queue-stall alert collapsed onto the
            # same "?" dedupe key and distinct stalled runs were suppressed
            # as recurrences of each other.
            self._raise_alert(
                repo, "queue_stall", run.get("id", "?"),
                detail=f"queued {age_sec / 60:.0f}m (threshold {self.config.queue_threshold_min:.0f}m), "
                       f"run: {run.get('name', '?')}")

    def _check_gate_results(self, repo: str) -> None:
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
                if conclusion in ("failure", "timed_out"):
                    self._raise_alert(
                        repo, "gate_failure", check.get("name", "?"),
                        detail=f"conclusion={conclusion}, branch={branch}, sha={sha[:8]}")

    def _check_drift_scan(self, repo: str) -> None:
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
        # Check if the latest run failed.
        if latest.get("conclusion") == "failure":
            self._raise_alert(
                repo, "drift_failed", "?",
                detail=f"latest drift scan failed: {latest.get('html_url', '')}")
            return

        # Check recency: must have completed within one period + grace.
        completed_at = _parse_iso(latest.get("completed_at"))
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

    def _raise_alert(self, repo: str, check_class: str, runner: str, detail: str) -> None:
        """Raise an alert. Sprint 4 adds dedupe + GitHub issue filing."""
        if self.alert_sink is not None:
            self.alert_sink.raise_alert(repo=repo, check_class=check_class,
                                        runner=runner, detail=detail)
        else:
            # No alert sink configured (Sprint 3 stub): log loudly.
            log.warning("ALERT [%s/%s/%s] %s", repo, check_class, runner, detail)



