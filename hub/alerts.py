"""hub.alerts — deduplicated failure alerts (D6, mon-alert-01).

The hub raises alerts as GitHub issues on the affected repo, deduplicated
by (repo, check-class, runner): one open issue per key. Recurrence is
posted as a comment on the existing issue instead of filing a new one.
Every alert is appended to an append-only JSONL alert log on the hub volume.

Notifier interface: AlertSink is the abstract base. GitHubIssueNotifier
is the default channel (Q1). Additional notifiers (email, webhook) plug in
behind the same interface — out of scope for v1 beyond the interface.

Stdlib-only: urllib.request for GitHub API calls.

// spec: mon-alert-01
"""

from __future__ import annotations

import abc
import json
import logging
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .config import Config

log = logging.getLogger("hub.alerts")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class AlertSink(abc.ABC):
    """Abstract notifier interface. Implementations deliver alerts to a channel."""

    @abc.abstractmethod
    def raise_alert(self, repo: str, check_class: str, runner: str, detail: str) -> None:
        raise NotImplementedError


class GitHubIssueNotifier(AlertSink):
    """Files (or comments on) a GitHub issue per (repo, check-class, runner).

    Dedupe strategy: search for an open issue with the exact title pattern
    `[devgate-monitor] {check_class}: {runner}` in the target repo. If found,
    post a comment; if not, file a new issue with label `devgate-monitor`.

    The JSONL alert log is appended regardless of channel success — the log
    is the audit trail, the issue is the notification.
    """

    LABEL = "devgate-monitor"

    def __init__(self, api_base: str, token: str, alerts_dir: str) -> None:
        self.api_base = api_base.rstrip("/")
        self.token = token
        self.alerts_dir = Path(alerts_dir)
        self._lock = threading.Lock()
        # In-memory dedupe cache: (repo, check_class, runner) -> issue_number.
        # Avoids a search API call on every recurrence within the same process.
        self._open_issues: dict[tuple[str, str, str], int] = {}

    def raise_alert(self, repo: str, check_class: str, runner: str, detail: str) -> None:
        """Deliver an alert: append to JSONL log + file/comment GitHub issue."""
        # 1. Always append to the JSONL audit log (mon-alert-01).
        self._append_log(repo, check_class, runner, detail)

        # 2. Deliver via GitHub issue (the default channel, Q1).
        if not self.token:
            log.warning("ALERT [%s/%s/%s] %s (no GITHUB_TOKEN — issue filing skipped)",
                        repo, check_class, runner, detail)
            return

        key = (repo, check_class, runner)
        title = f"[devgate-monitor] {check_class}: {runner}"
        body = self._format_body(repo, check_class, runner, detail)

        try:
            issue_number = self._find_open_issue(repo, title)
            if issue_number is not None:
                # Recurrence: comment on the existing issue.
                self._comment_on_issue(repo, issue_number, body)
                log.info("ALERT recurrence commented on #%d in %s", issue_number, repo)
            else:
                # First occurrence: file a new issue.
                issue_number = self._file_issue(repo, title, body)
                if issue_number is not None:
                    self._open_issues[key] = issue_number
                    log.info("ALERT filed issue #%d in %s", issue_number, repo)
        except Exception as e:  # noqa: BLE001 — alert delivery must never crash the hub
            log.error("alert delivery failed for %s/%s/%s: %s", repo, check_class, runner, e)

    def _append_log(self, repo: str, check_class: str, runner: str, detail: str) -> None:
        """Append one line to the JSONL alert log (append-only, mon-alert-01)."""
        with self._lock:
            self.alerts_dir.mkdir(parents=True, exist_ok=True)
            # One file per day for easy rotation/inspection.
            day = _now_iso()[:10]  # YYYY-MM-DD
            log_file = self.alerts_dir / f"alerts-{day}.jsonl"
            entry = {
                "ts": _now_iso(),
                "repo": repo,
                "check_class": check_class,
                "runner": runner,
                "detail": detail,
            }
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

    def _find_open_issue(self, repo: str, title: str) -> int | None:
        """Search for an open issue with the exact title. Returns issue number or None."""
        # Fast path: in-memory cache.
        key = self._key_from_title(repo, title)
        if key and key in self._open_issues:
            return self._open_issues[key]

        # GitHub search API: repo + is:issue + is:open + in:title.
        query = f"repo:{repo} is:issue is:open in:title \"{title}\""
        url = f"{self.api_base}/search/issues?q={urllib.parse.quote(query)}&per_page=1"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode())
                items = body.get("items", [])
                if items:
                    number = items[0]["number"]
                    # Cache it.
                    if key:
                        self._open_issues[key] = number
                    return number
        except urllib.error.HTTPError as e:
            log.warning("issue search failed for %s: HTTP %d", repo, e.code)
        return None

    def _key_from_title(self, repo: str, title: str) -> tuple[str, str, str] | None:
        """Reverse-parse the title pattern back to a dedupe key."""
        prefix = "[devgate-monitor] "
        if not title.startswith(prefix):
            return None
        rest = title[len(prefix):]
        # Pattern: "{check_class}: {runner}"
        if ":" in rest:
            check_class, runner = rest.split(":", 1)
            return (repo, check_class.strip(), runner.strip())
        return None

    def _file_issue(self, repo: str, title: str, body: str) -> int | None:
        """File a new GitHub issue. Returns the issue number or None on failure."""
        url = f"{self.api_base}/repos/{repo}/issues"
        payload = json.dumps({
            "title": title,
            "body": body,
            "labels": [self.LABEL],
        }).encode()
        req = urllib.request.Request(url, data=payload, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                issue = json.loads(resp.read().decode())
                return issue.get("number")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode() if e.fp else ""
            log.error("issue filing failed for %s: HTTP %d %s", repo, e.code, err_body[:200])
        return None

    def _comment_on_issue(self, repo: str, issue_number: int, body: str) -> None:
        """Post a comment on an existing issue (recurrence)."""
        url = f"{self.api_base}/repos/{repo}/issues/{issue_number}/comments"
        payload = json.dumps({"body": body}).encode()
        req = urllib.request.Request(url, data=payload, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()
        except urllib.error.HTTPError as e:
            log.error("issue comment failed for %s#%d: HTTP %d", repo, issue_number, e.code)

    def _format_body(self, repo: str, check_class: str, runner: str, detail: str) -> str:
        return (
            f"## DevGate Monitor Alert\n\n"
            f"- **Repo:** `{repo}`\n"
            f"- **Check:** `{check_class}`\n"
            f"- **Runner:** `{runner}`\n"
            f"- **Time:** {_now_iso()}\n\n"
            f"### Detail\n\n{detail}\n"
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        }


class NullNotifier(AlertSink):
    """No-op notifier: logs alerts but files no issues. Used when Q1 = null."""

    def raise_alert(self, repo: str, check_class: str, runner: str, detail: str) -> None:
        log.warning("ALERT [%s/%s/%s] %s", repo, check_class, runner, detail)


def build_notifier(config: Config) -> AlertSink:
    """Factory: pick the notifier based on HUB_ALERT_CHANNEL (Q1)."""
    channel = config.alert_channel  # "github_issue" | "null"
    if channel == "github_issue":
        return GitHubIssueNotifier(
            api_base=config.github_api_base,
            token=os.environ.get("GITHUB_TOKEN", ""),
            alerts_dir=config.alerts_dir,
        )
    else:
        return NullNotifier()
