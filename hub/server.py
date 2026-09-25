"""hub.server — /enroll, /heartbeat, /health over ThreadingHTTPServer.

Endpoint contract (archived design D4):
  POST /enroll    one-time enrollment token -> per-runner heartbeat token
                  200 ok | 401 unknown_or_revoked_token | 409 already_enrolled | 400 bad_request
  POST /heartbeat freshness + host health for a verified runner
                  200 ok | 401 unknown_or_revoked_token
  GET  /health    no auth; liveness + dead-man-switch timestamps (risk table)

The server never echoes secrets. Token verification lives in hub/tokens.py;
this handler stays thin.

// spec: mon-hub-01
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import tokens
from .config import Config
from .registry import UNREPORTED, Registry

REPO_RE = re.compile(r"^[^/]+/[^/]+$")


class HubState:
    """Shared mutable state: registry + liveness timestamps."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.registry = Registry(config.registry_path)
        self.started_at = datetime.now(timezone.utc)
        self.last_poll_at: datetime | None = None
        self.last_alert_at: datetime | None = None
        # Set by main() when the poll thread is started. A watcher reading
        # /health must be able to tell "polling is disabled, so last_poll_at
        # will stay null forever" from "polling is enabled but the loop died" —
        # otherwise an unconfigured hub reads as a dead one.
        self.polling_enabled: bool = False
        self._lock = threading.Lock()

    def note_poll(self) -> None:
        """Record that a full poll cycle completed (drives /health staleness)."""
        self.last_poll_at = datetime.now(timezone.utc)

    # // spec: mon-deadman-01 — the hub-side half of the requirement: the
    # /health contract a spoke watchdog reads (polling_enabled separates
    # "polling off, null by design" from "loop wedged"). The spoke half
    # (timer + unit failure) is scripts/hub-watchdog.sh, documented in
    # docs/runner-monitor-monitor-hub.md.

    def with_registry(self, fn):
        """Run fn(registry) under the state lock, saving on success."""
        with self._lock:
            result = fn(self.registry)
            if result is not False:
                self.registry.save()
            return result


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


class HubHandler(BaseHTTPRequestHandler):
    server_version = "DevGateMonitor/1.0"

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(length).decode()) if length else None
        except (ValueError, UnicodeDecodeError):
            return None

    def log_message(self, fmt, *args):  # keep test output quiet; hub logs via main
        pass

    # --- routes -------------------------------------------------------------

    def do_GET(self):  # noqa: N802 (http.server API)
        if self.path == "/health":
            state: HubState = self.server.hub_state
            now = datetime.now(timezone.utc)
            uptime = (now - state.started_at).total_seconds()
            iso = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None  # noqa: E731
            self._send(200, {
                "ok": True,
                "last_poll_at": iso(state.last_poll_at),
                "last_alert_at": iso(state.last_alert_at),
                "registered_runners": len(state.registry.runners()),
                "uptime_sec": uptime,
                # Watchdogs need these to judge staleness without guessing:
                # polling_enabled=false means last_poll_at is null by design.
                "polling_enabled": state.polling_enabled,
                "poll_interval_sec": state.config.poll_interval_sec,
            })
        else:
            self._send(404, {"ok": False, "error": "not_found"})

    def do_POST(self):  # noqa: N802 (http.server API)
        state: HubState = self.server.hub_state
        if self.path == "/enroll":
            self._handle_enroll(state)
        elif self.path == "/heartbeat":
            self._handle_heartbeat(state)
        elif self.path == "/revoke":
            self._handle_revoke(state)
        else:
            self._send(404, {"ok": False, "error": "not_found"})

    # --- /enroll (mon-enroll-01) ---------------------------------------------

    def _handle_enroll(self, state: HubState) -> None:
        data = self._read_json()
        if not isinstance(data, dict):
            self._send(400, {"ok": False, "error": "bad_request", "detail": "json object required"})
            return
        runner_name = data.get("runner_name")
        repo = data.get("repo")
        presented = data.get("enrollment_token")
        labels = data.get("labels") or []
        host_alias = data.get("host_alias") or ""
        if not runner_name or not REPO_RE.match(repo or ""):
            self._send(400, {"ok": False, "error": "bad_request",
                             "detail": "runner_name and repo OWNER/REPO required"})
            return
        if state.registry.find_runner(runner_name) is not None:
            self._send(409, {"ok": False, "error": "already_enrolled"})
            return
        # One-time enrollment token: verify AND consume before recording identity.
        def do_enroll(reg):
            if not reg.consume_enrollment_token(presented or ""):
                return False
            runner = reg.enroll(runner_name, repo, labels, host_alias)
            return {"ok": True, "runner_name": runner_name,
                    "heartbeat_token": runner["heartbeat_token"]}

        result = state.with_registry(do_enroll)
        if result is False:
            self._send(401, {"ok": False, "error": "unknown_or_revoked_token"})
        else:
            self._send(200, result)

    # --- /heartbeat (mon-enroll-01, mon-online-01) -----------------------------

    def _handle_heartbeat(self, state: HubState) -> None:
        data = self._read_json()
        if not isinstance(data, dict):
            self._send(400, {"ok": False, "error": "bad_request", "detail": "json object required"})
            return
        runner_name = data.get("runner_name") or ""
        presented = data.get("heartbeat_token") or ""

        def do_heartbeat(reg):
            if not reg.verify_heartbeat_token(runner_name, presented):
                return False
            # The image fields and the fleet sweep's state are read
            # presence-aware: a body that omits them must not clear a host's
            # last report, while a body that sends an explicit null must
            # (registry.UNREPORTED says why).
            reg.heartbeat(runner_name, data.get("last_job_seen"),
                          data.get("disk_ok"), data.get("podman_ok"),
                          data.get("image_digest", UNREPORTED),
                          data.get("image_reason", UNREPORTED),
                          data.get("scan_state", UNREPORTED))
            return {"ok": True}

        result = state.with_registry(do_heartbeat)
        if result is False:
            self._send(401, {"ok": False, "error": "unknown_or_revoked_token"})
        else:
            self._send(200, result)


    # --- /revoke (mon-enroll-01) ---------------------------------------------

    def _handle_revoke(self, state: HubState) -> None:
        """Revoke a runner's heartbeat token. Authenticated by the token itself."""
        data = self._read_json()
        if not isinstance(data, dict):
            self._send(400, {"ok": False, "error": "bad_request", "detail": "json object required"})
            return
        runner_name = data.get("runner_name") or ""
        presented = data.get("heartbeat_token") or ""

        def do_revoke(reg):
            # Verify the token belongs to this runner before revoking.
            if not reg.verify_heartbeat_token(runner_name, presented):
                return False
            reg.revoke(runner_name)
            return {"ok": True, "runner_name": runner_name}

        result = state.with_registry(do_revoke)
        if result is False:
            self._send(401, {"ok": False, "error": "unknown_or_revoked_token"})
        else:
            self._send(200, result)


def create_server(config: Config, bind: tuple[str, int] | None = None) -> ThreadingHTTPServer:
    """Build the hub server. bind=(host, port) with port 0 lets tests take an
    ephemeral port; the bound port is read back from server.server_address."""
    host, port = bind if bind else (config.bind_host, config.bind_port)
    server = ThreadingHTTPServer((host, port), HubHandler)
    server.hub_state = HubState(config)  # type: ignore[attr-defined]
    return server
