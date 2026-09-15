"""Tests for hub/alerts.py (Sprint 4.1–4.2): dedupe + GitHub-issue notifier.

Verifies:
  - JSONL alert log is appended on every raise_alert (mon-alert-01)
  - First occurrence files a new issue with the devgate-monitor label
  - Recurrence comments on the existing open issue instead of filing a new one
  - NullNotifier logs but files nothing
  - build_notifier factory picks the right implementation from config

Dual-runnable: pytest collects test_*; `python3 tests/test_hub_alerts.py` runs them too.
"""
import json
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.alerts import (  # noqa: E402
    AlertSink,
    GitHubIssueNotifier,
    NullNotifier,
    build_notifier,
)
from hub.config import Config  # noqa: E402


# ---------------------------------------------------------------------------
# Fake GitHub API for issue filing / search / comments
# ---------------------------------------------------------------------------

class FakeGitHubIssuesHandler(BaseHTTPRequestHandler):
    """Minimal fake for the GitHub issues API used by GitHubIssueNotifier."""

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        # Search endpoint: /search/issues?q=...
        if self.path.startswith("/search/issues"):
            routes: dict = self.server.routes  # type: ignore[attr-defined]
            handler = routes.get("search")
            if handler:
                status, body = handler()
                self._respond(status, body)
            else:
                self._respond(200, {"items": []})
        else:
            self._respond(404, {"message": "not found"})

    def do_POST(self):
        routes: dict = self.server.routes  # type: ignore[attr-defined]
        length = int(self.headers.get("Content-Length", 0))
        body_raw = self.rfile.read(length).decode() if length else "{}"
        payload = json.loads(body_raw)

        if "/issues" in self.path and "/comments" not in self.path:
            handler = routes.get("create_issue")
            if handler:
                status, resp_body = handler(payload)
                self._respond(status, resp_body)
            else:
                # Default: file a new issue with an incrementing number.
                self.server.issue_counter += 1  # type: ignore[attr-defined]
                self._respond(201, {"number": self.server.issue_counter})  # type: ignore[attr-defined]
        elif "/comments" in self.path:
            handler = routes.get("comment")
            if handler:
                status, resp_body = handler(payload)
                self._respond(status, resp_body)
            else:
                self._respond(201, {"id": 1})
        else:
            self._respond(404, {"message": "not found"})

    def _respond(self, status: int, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def _start_fake_gh(routes: dict) -> tuple[ThreadingHTTPServer, int]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeGitHubIssuesHandler)
    server.routes = routes  # type: ignore[attr-defined]
    server.issue_counter = 0  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_jsonl_log_appended(tmp_path):
    """Every raise_alert appends a line to the JSONL alert log (mon-alert-01)."""
    alerts_dir = str(tmp_path / "alerts")
    notifier = GitHubIssueNotifier(api_base="http://unused", token="", alerts_dir=alerts_dir)

    notifier.raise_alert("owner/repo", "queue_stall", "r1", "queued 45m")
    notifier.raise_alert("owner/repo", "runner_offline", "r2", "heartbeat stale")

    # Find the daily log file.
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = Path(alerts_dir) / f"alerts-{day}.jsonl"
    assert log_file.exists(), f"expected {log_file}"
    lines = log_file.read_text().strip().splitlines()
    assert len(lines) == 2, f"expected 2 lines, got {len(lines)}"

    entry1 = json.loads(lines[0])
    assert entry1["repo"] == "owner/repo"
    assert entry1["check_class"] == "queue_stall"
    assert entry1["runner"] == "r1"
    assert entry1["detail"] == "queued 45m"
    assert "ts" in entry1

    entry2 = json.loads(lines[1])
    assert entry2["check_class"] == "runner_offline"
    assert entry2["runner"] == "r2"


def test_first_alert_files_new_issue(tmp_path):
    """First occurrence of (repo, check-class, runner) files a new issue."""
    alerts_dir = str(tmp_path / "alerts")
    created_issues: list[dict] = []

    def create_handler(payload):
        created_issues.append(payload)
        return (201, {"number": 42})

    server, port = _start_fake_gh({
        "search": lambda: (200, {"items": []}),  # no existing open issue
        "create_issue": create_handler,
    })
    try:
        notifier = GitHubIssueNotifier(
            api_base=f"http://127.0.0.1:{port}", token="test-token", alerts_dir=alerts_dir)
        notifier.raise_alert("owner/repo", "queue_stall", "r1", "queued 45m")

        assert len(created_issues) == 1, f"expected 1 issue created, got {len(created_issues)}"
        issue = created_issues[0]
        assert issue["title"] == "[devgate-monitor] queue_stall: r1"
        assert "devgate-monitor" in issue["labels"]
        assert "owner/repo" in issue["body"]
    finally:
        server.shutdown()


def test_recurrence_comments_not_new_issue(tmp_path):
    """Second alert for the same key comments on the open issue (mon-alert-01)."""
    alerts_dir = str(tmp_path / "alerts")
    comments: list[dict] = []
    created_issues: list[dict] = []

    def create_handler(payload):
        created_issues.append(payload)
        return (201, {"number": 7})

    def comment_handler(payload):
        comments.append(payload)
        return (201, {"id": 999})

    # Search finds the existing open issue #7.
    server, port = _start_fake_gh({
        "search": lambda: (200, {"items": [{"number": 7}]}),
        "create_issue": create_handler,
        "comment": comment_handler,
    })
    try:
        notifier = GitHubIssueNotifier(
            api_base=f"http://127.0.0.1:{port}", token="test-token", alerts_dir=alerts_dir)

        # First alert: search finds nothing → files new issue.
        server.routes["search"] = lambda: (200, {"items": []})  # type: ignore[attr-defined]
        notifier.raise_alert("owner/repo", "queue_stall", "r1", "queued 45m")
        assert len(created_issues) == 1

        # Second alert: search now finds issue #7 → comments instead.
        server.routes["search"] = lambda: (200, {"items": [{"number": 7}]})  # type: ignore[attr-defined]
        notifier.raise_alert("owner/repo", "queue_stall", "r1", "queued 50m")
        assert len(created_issues) == 1, "should NOT file a second issue"
        assert len(comments) == 1, f"expected 1 comment, got {len(comments)}"
        assert "queued 50m" in comments[0]["body"]
    finally:
        server.shutdown()


def test_dedupe_by_different_runner(tmp_path):
    """Different runner = different key = new issue (not a comment)."""
    alerts_dir = str(tmp_path / "alerts")
    created_issues: list[dict] = []

    def create_handler(payload):
        created_issues.append(payload)
        return (201, {"number": len(created_issues) + 1})

    server, port = _start_fake_gh({
        "search": lambda: (200, {"items": []}),
        "create_issue": create_handler,
    })
    try:
        notifier = GitHubIssueNotifier(
            api_base=f"http://127.0.0.1:{port}", token="test-token", alerts_dir=alerts_dir)
        notifier.raise_alert("owner/repo", "queue_stall", "r1", "stall 1")
        notifier.raise_alert("owner/repo", "queue_stall", "r2", "stall 2")

        assert len(created_issues) == 2, f"expected 2 issues (different runners), got {len(created_issues)}"
    finally:
        server.shutdown()


def test_null_notifier_logs_only(tmp_path):
    """NullNotifier makes no HTTP calls but still writes the JSONL audit log."""
    alerts_dir = str(tmp_path / "alerts")
    notifier = NullNotifier(alerts_dir=alerts_dir)
    # Should not raise any exception.
    notifier.raise_alert("owner/repo", "queue_stall", "r1", "detail")
    # mon-alert-01: the append-only audit trail must exist even with no
    # GitHub channel configured (local-only must not mean no evidence).
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = Path(alerts_dir) / f"alerts-{day}.jsonl"
    assert log_file.exists(), f"expected audit log {log_file}"
    entry = json.loads(log_file.read_text().strip())
    assert entry["repo"] == "owner/repo"
    assert entry["check_class"] == "queue_stall"
    assert entry["runner"] == "r1"
    assert entry["detail"] == "detail"


def test_recurrence_comment_cooldown(tmp_path):
    """Repeat recurrences are suppressed during the cooldown window."""
    alerts_dir = str(tmp_path / "alerts")
    comments: list[dict] = []

    def comment_handler(payload):
        comments.append(payload)
        return (201, {"id": 1})

    # Search finds an existing open issue #42 on every call.
    server, port = _start_fake_gh({
        "search": lambda: (200, {"items": [{"number": 42}]}),
        "comment": comment_handler,
    })
    try:
        notifier = GitHubIssueNotifier(
            api_base=f"http://127.0.0.1:{port}", token="t",
            alerts_dir=alerts_dir, comment_cooldown_sec=3600.0)
        notifier.raise_alert("owner/repo", "queue_stall", "r1", "first")
        notifier.raise_alert("owner/repo", "queue_stall", "r1", "second")
        notifier.raise_alert("owner/repo", "queue_stall", "r1", "third")
        # Only the first recurrence escapes the cooldown.
        assert len(comments) == 1, f"expected 1 comment, got {len(comments)}"
        # The audit log still records every occurrence (mon-alert-01).
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        lines = (Path(alerts_dir) / f"alerts-{day}.jsonl").read_text().strip().splitlines()
        assert len(lines) == 3, f"expected 3 audit lines, got {len(lines)}"
    finally:
        server.shutdown()


def test_build_notifier_factory_github_issue(tmp_path):
    """build_notifier returns GitHubIssueNotifier when channel=github_issue."""
    config = Config()
    config.alert_channel = "github_issue"
    config.data_dir = str(tmp_path)
    notifier = build_notifier(config)
    assert isinstance(notifier, GitHubIssueNotifier)


def test_build_notifier_factory_null(tmp_path):
    """build_notifier returns a local-only notifier when channel=null."""
    config = Config()
    config.alert_channel = "null"
    config.data_dir = str(tmp_path)
    notifier = build_notifier(config)
    assert isinstance(notifier, NullNotifier)
    # Local-only must still write the audit log (mon-alert-01).
    notifier.raise_alert("owner/repo", "queue_stall", "r1", "detail")
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert (Path(config.alerts_dir) / f"alerts-{day}.jsonl").exists()


def test_alert_sink_is_abstract():
    """AlertSink cannot be instantiated directly."""
    try:
        AlertSink()  # type: ignore[abstract]
        assert False, "should have raised TypeError"
    except TypeError:
        pass


def main() -> int:
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))


if __name__ == "__main__":
    main()
