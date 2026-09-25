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
import time
import urllib.error
import urllib.request
from datetime import datetime

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

    def __init__(self, api_base: str, token: str, backoff_max: int = 120) -> None:
        self.api_base = api_base.rstrip("/")
        self.token = token
        self.backoff_max = backoff_max
        self._last_request_time = 0.0

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
        """GET with exponential backoff on 403/429. Returns None if all retries exhausted."""
        for attempt in range(max_retries):
            status, body = self.get(path)
            if status == 200:
                return (status, body)
            if status in (403, 429):
                # Rate limited — honor Retry-After header if present.
                retry_after = body.get("retry_after") or body.get("X-Retry-After")
                wait = min(int(retry_after) if retry_after else (2 ** attempt) * 10, self.backoff_max)
                log.warning("rate limited on %s (attempt %d/%d), backing off %ds",
                            path, attempt + 1, max_retries, wait)
                time.sleep(wait)
                continue
            # Other errors: return immediately.
            return (status, body)
        return None
