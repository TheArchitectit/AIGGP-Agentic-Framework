"""Tests for hub/monitor.py (Sprint 3.1–3.3): GitHub polling loop.

Uses a fake GitHub API server (stdlib http.server) so no real network calls
are made. Verifies:
  - runner online detection (API status + heartbeat freshness)
  - queue-drain detection (queued run older than threshold)
  - gate-result tracking (check-run conclusion failure/timed_out)
  - drift-scan recency (overdue or failed scan)
  - rate-limit backoff on 403/429

Dual-runnable: pytest collects test_*; `python3 tests/test_hub_monitor.py` runs them too.
"""
import json
import os
import socket
import sys
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.config import Config  # noqa: E402
from hub.github_client import GitHubClient, parse_iso  # noqa: E402
from hub.monitor import MonitorLoop  # noqa: E402
from hub.server import HubState  # noqa: E402

# ---------------------------------------------------------------------------
# Fake GitHub API server (per-instance routes to avoid cross-test pollution)
# ---------------------------------------------------------------------------

class FakeGitHubHandler(BaseHTTPRequestHandler):
    """Routes GitHub API paths to canned responses configured per-server."""

    def log_message(self, fmt, *args):
        pass  # silence

    def do_GET(self):
        routes: dict = self.server.routes  # type: ignore[attr-defined]
        handler = routes.get(self.path)
        if handler is None:
            self._respond(404, {"message": "not found"})
            return
        status, body = handler()
        self._respond(status, body)

    def _respond(self, status: int, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def _start_fake_gh(routes: dict) -> tuple[ThreadingHTTPServer, int]:
    """Start a fake GitHub API server with the given routes. Returns (server, port)."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeGitHubHandler)
    server.routes = routes  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]

def _wire_gh(monitor: MonitorLoop, port: int) -> None:
    """Point a monitor at the fake server, with backoff off so retries do not sleep."""
    monitor.client.api_base = f"http://127.0.0.1:{port}"
    monitor.client.backoff_max = 0

def _hub_state(tmp_path) -> HubState:
    """A HubState whose data dir is under tmp_path, so no test writes to the real one."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    return HubState(config)

def _enroll(state: HubState, name: str, repo: str, host: str = "host1"):
    """Consume a one-shot enrollment token and return the enrolled runner dict.

    The token value is never asserted on, only that enrollment went through the
    one-shot path — so it is derived from the name rather than repeated at each
    call site.
    """
    token = f"tok-{name}"
    state.registry.add_enrollment_token(token)
    state.registry.consume_enrollment_token(token)
    record, _plaintext = state.registry.enroll(name, repo, ["devgate"], host)
    return record


class _CollectSink:
    """Records alerts as (repo, check_class, runner, detail).

    Every test here needs only `check_class` (or the runner name); both are
    reachable from the 4-tuple, so one sink serves every monitor slice.
    """

    def __init__(self):
        self.alerts = []

    def raise_alert(self, repo, check_class, runner, detail):
        self.alerts.append((repo, check_class, runner, detail))

    @property
    def classes(self) -> list[str]:
        return [a[1] for a in self.alerts]
