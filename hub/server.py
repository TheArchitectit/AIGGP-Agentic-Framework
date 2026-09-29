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

import copy
import json
import re
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import tokens
from .config import Config
from .registry import UNREPORTED, Registry

# A strict owner/name: the repo string flows into API paths
# (f"/repos/{repo}/...") and the registry schema. The old `[^/]+` accepted
# query strings, `..` segments, and trailing newlines — none of which are
# valid in a repository name, all of which alter the request. `\Z`, not `$`:
# Python's `$` tolerates exactly one trailing newline.
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")

# Bodies are read before any auth check (/enroll authenticates via its token,
# which lives IN the body), so trusting Content-Length hands any client an
# unauthenticated allocation up to 2 GB — doubled again by decode(). Every
# legitimate payload here is a small JSON object. The ceiling is
# Config.max_body_bytes (default 64 KiB; operators may lower it further).
MAX_BODY_BYTES = 64 * 1024

# Returned by a locked enroll when the name is taken: the duplicate check must
# run inside the critical section (a pre-check outside it let two concurrent
# enrolls with different valid tokens both pass and both append), and the
# caller still needs 409 distinct from 401.
ALREADY_ENROLLED = object()


class PayloadTooLarge(Exception):
    """Content-Length over MAX_BODY_BYTES — raised before the body is read."""


class InvalidContentLength(Exception):
    """Content-Length < 0 — refused BEFORE any read, answered as 400 by do_POST.

    BufferedReader.read(n) with a negative n reads until EOF: on a socket that
    is "hang until the client hangs up", so one unauthenticated connection
    pins a request thread forever. A hub's spokes page on /health staleness;
    enough pinned threads and the page fires while the hub is merely wedged.
    Live-verified 2026-09-27 — the cap above only bounded the positive side.
    """


# Per-field caps: the body cap bounds the REQUEST, not what one field can do
# to an issue body or a fleet table later. A 60 KB image_reason belongs in no
# GitHub issue; labels are names, not payloads.
FIELD_CAPS = {"image_digest": 512, "image_reason": 1024, "last_job_seen": 256}
MAX_LABELS = 64
MAX_LABEL_LEN = 128
MAX_SCAN_REPOS = 256
MAX_SCAN_REPO_NAME = 256
MAX_SCAN_FIELD_LEN = 64


def _labels_ok(labels) -> bool:
    return (isinstance(labels, list) and len(labels) <= MAX_LABELS
            and all(isinstance(l, str) and len(l) <= MAX_LABEL_LEN
                    for l in labels))


def _scan_state_ok(state) -> bool:
    """Structural bound on the fleet-sweep report, not a vocabulary check.

    scan_view renders any state word it does not whitelist as unknown, so the
    boundary only has to guarantee shape and size — a hostile spoke must not
    park a 60 KB string inside one repo record, but it is the renderer's job,
    not the transport's, to judge the words.
    """
    if not isinstance(state, dict):
        return False
    repos = state.get("repos")
    if repos is None:
        return True
    if not isinstance(repos, list) or len(repos) > MAX_SCAN_REPOS:
        return False
    for record in repos:
        if not isinstance(record, dict):
            return False
        for key, value in record.items():
            if isinstance(value, str):
                cap = MAX_SCAN_REPO_NAME if key == "name" else MAX_SCAN_FIELD_LEN
                if len(value) > cap:
                    return False
            elif not isinstance(value, (int, bool, type(None))):
                return False
    return True


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
            if result is not False and result is not ALREADY_ENROLLED:
                self.registry.save()
            return result

    def runners_snapshot(self):
        """Deep copies of the runner records, taken under the lock.

        HTTP threads mutate runner dicts in place (heartbeat writes
        last_heartbeat, image_digest, image_reason and scan_state as separate
        assignments) while the monitor thread reads them field by field. An
        unlocked read can land between those assignments — a new digest with
        the old reason — and the readiness checks that gate on the pair would
        decide from a report that never existed.
        """
        with self._lock:
            return copy.deepcopy(self.registry.runners())

    # Audit-side name (F10) for the same torn-read-safe snapshot. Two names,
    # one lock + deep copy — callers on either lineage keep working.
    def snapshot_runners(self):
        return self.runners_snapshot()




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
        except ValueError:
            return None
        if length < 0:
            # Refused BEFORE the read: a negative length would otherwise send
            # rfile.read(-1) into read-until-EOF, pinning this thread until
            # the client hangs up (see InvalidContentLength).
            raise InvalidContentLength()
        cap = getattr(self.server.hub_state.config, "max_body_bytes", MAX_BODY_BYTES)
        if length > cap:
            # Refused BEFORE reading: the 413 is sent by do_POST, which owns
            # the response so a handler never answers twice.
            raise PayloadTooLarge()
        try:
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
                # The LIVE set, like the monitor's per-cycle filter: revoked
                # rows stay in the registry for audit but must not make
                # /health promise monitoring the hub will never perform.
                "registered_runners": sum(
                    1 for r in state.registry.runners() if r.get("enrolled")),
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
        try:
            if self.path == "/enroll":
                self._handle_enroll(state)
            elif self.path == "/heartbeat":
                self._handle_heartbeat(state)
            elif self.path == "/revoke":
                self._handle_revoke(state)
            else:
                self._send(404, {"ok": False, "error": "not_found"})
        except PayloadTooLarge:
            # Raised before the body was read; the connection is HTTP/1.0 and
            # closes on this response, so the unread body is discarded.
            self._send(413, {"ok": False, "error": "body_too_large",
                             "max_bytes": getattr(self.server.hub_state.config,
                                                  "max_body_bytes", MAX_BODY_BYTES)})
        except InvalidContentLength:
            # The negative length was refused before reading; 400 is correct.
            # No body was consumed, so nothing drains, and a malicious repeat
            # can be rate-limited at the proxy / TLS layer.
            self._send(400, {"ok": False, "error": "bad_request",
                             "detail": "invalid_content_length"})

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
        if not isinstance(runner_name, str) or not runner_name \
                or not REPO_RE.match(repo or ""):
            self._send(400, {"ok": False, "error": "bad_request",
                             "detail": "runner_name and repo OWNER/REPO required"})
            return
        # Rejected before the token is consumed and before the 409 probe
        # (both exact-name): a whitespace variant of a live name would enroll
        # as a second live row for one physical host — double alerts, /health
        # inflated. Trimming instead is worse: the spoke freezes the name it
        # sent into its env file, so a trimmed row would 401 every heartbeat
        # forever. Case is deliberately untouched — it is credential-bearing.
        if runner_name != runner_name.strip():
            self._send(400, {"ok": False, "error": "bad_request",
                             "detail": "runner_name has surrounding whitespace"})
            return
        if not _labels_ok(labels):
            self._send(400, {"ok": False, "error": "bad_request",
                             "detail": "labels must be a list of at most 64 short strings"})
            return
        # One-time enrollment token: verify AND consume before recording
        # identity. The duplicate-name check runs inside the same locked
        # section as the consume: the old pre-check sat outside the lock, so
        # two concurrent enrolls with the same name and two different valid
        # tokens both passed it and both appended — a duplicate registry entry
        # whose second token keeps working while its twin's health goes stale.
        # Checking before consuming also means a rejected duplicate spends no
        # token.
        def do_enroll(reg):
            if reg.find_runner(runner_name) is not None:
                return ALREADY_ENROLLED
            if not reg.consume_enrollment_token(presented or ""):
                return False
            runner, heartbeat_token = reg.enroll(runner_name, repo, labels, host_alias)
            return {"ok": True, "runner_name": runner_name,
                    "heartbeat_token": heartbeat_token}

        result = state.with_registry(do_enroll)
        if result is ALREADY_ENROLLED:
            self._send(409, {"ok": False, "error": "already_enrolled"})
        elif result is False:
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
        for key, cap in FIELD_CAPS.items():
            value = data.get(key)
            if value is not None and (not isinstance(value, str) or len(value) > cap):
                self._send(400, {"ok": False, "error": "bad_request",
                                 "detail": f"{key} must be a string of at most {cap} characters"})
                return
        for key in ("disk_ok", "podman_ok"):
            if key in data and data[key] is not None and not isinstance(data[key], bool):
                self._send(400, {"ok": False, "error": "bad_request",
                                 "detail": f"{key} must be a boolean or null"})
                return
        if data.get("scan_state") is not None and not _scan_state_ok(data["scan_state"]):
            self._send(400, {"ok": False, "error": "bad_request",
                             "detail": "scan_state must be a bounded fleet-sweep report"})
            return

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
