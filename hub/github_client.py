"""hub.github_client — the GitHub REST transport the monitor polls with.

Split out of `hub/monitor.py`, which had reached DevGate's own 500-line hard
limit (scripts/regression_sizes.py). The seam is the useful part: the monitor
is the polling POLICY — which facts to check and what to alert on — and this
is the TRANSPORT, how one request is made and how a rate limit is survived.
Each half then states its subject in one docstring, and the monitor's line
budget goes to checks rather than to plumbing.

Stdlib-only: urllib.request, no pip dependencies.

// spec: mon-channels-01
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

log = logging.getLogger("hub.github_client")


def parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp; return None on failure."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class GitHubClient:
    """Minimal GitHub REST client (stdlib urllib). Backs off on 403/429."""

    def __init__(self, api_base: str, token: str, backoff_max: int = 120,
                 token_file: str = "") -> None:
        self.api_base = api_base.rstrip("/")
        self.token = token
        self.backoff_max = backoff_max
        self._last_request_time = 0.0
        # Optional path to re-read the token from; refresh_token() is a no-op
        # unless it is set, so a bare token argument is unchanged.
        self.token_file = token_file

    def refresh_token(self) -> None:
        """Re-read the token from `token_file`, if one was configured.

        The hub enrolls with a token GitHub can rotate (revoke/re-enroll), so
        re-reading each poll cycle lets a rotation take effect without a hub
        restart. An unreadable file keeps the current token rather than
        dropping to unauthenticated requests: a transient read error must not
        turn every check in that cycle into a silent 401.
        """
        if self.token_file and os.path.isfile(self.token_file):
            try:
                self.token = Path(self.token_file).read_text().strip()
            except OSError:
                pass  # keep the existing token

    def _request(self, method: str, path: str, body: dict | None = None,
                 accept: str = "application/vnd.github+json") -> tuple[int, dict | list, dict]:
        """Make an authenticated GitHub API request. Returns (status, parsed_body, headers)."""
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
                headers = dict(resp.headers)
                return resp.status, json.loads(raw) if raw else {}, headers
        except urllib.error.HTTPError as e:
            body_raw = e.read().decode() if e.fp else ""
            headers = dict(e.headers) if e.headers else {}
            try:
                parsed = json.loads(body_raw) if body_raw else {}
            except json.JSONDecodeError:
                parsed = {"message": body_raw[:200]}
            return e.code, parsed, headers

    def get(self, path: str) -> tuple[int, dict | list, dict]:
        return self._request("GET", path)

    def post(self, path: str, body: dict) -> tuple[int, dict | list, dict]:
        return self._request("POST", path, body=body)

    def get_with_backoff(self, path: str, max_retries: int = 3) -> tuple[int, dict | list] | None:
        """GET with exponential backoff on 403/429. Returns None if all retries exhausted."""
        for attempt in range(max_retries):
            status, body, headers = self.get(path)
            if status == 200:
                return (status, body)
            if status in (403, 429):
                # Rate limited. GitHub carries Retry-After in the response
                # HEADERS; the transport now returns them, so this reads the
                # real value rather than a body proxy field. A non-numeric
                # value falls back to backoff instead of raising — an exception
                # here skips the rest of that repo's checks for the cycle.
                retry_after = headers.get("Retry-After") if headers else None
                wait = (2 ** attempt) * 10
                if retry_after:
                    try:
                        wait = int(retry_after)
                    except (TypeError, ValueError):
                        pass
                wait = min(wait, self.backoff_max)
                log.warning("rate limited on %s (attempt %d/%d), backing off %ds",
                            path, attempt + 1, max_retries, wait)
                time.sleep(wait)
                continue
            # Other errors: return immediately.
            return (status, body)
        return None
