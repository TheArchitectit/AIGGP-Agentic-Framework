# // spec: GLF-02, GLF-13
"""hub.forge.api — the only component that talks the GitLab REST API.

The adapter (`hub.forge.adapter`) owns webhook and status payload shapes; this
client owns authenticated reads (the project walk that feeds the fleet
declaration). Gate scripts never import it, so forge credentials never reach a
gate.

Auth shape: a personal/project access token sent as the `PRIVATE-TOKEN`
header. The token is read by the caller from the environment and is never
written to a URL, a log line, or an exception message. A plain-HTTP base URL is
refused unless the caller explicitly opts in (a tailnet-only deployment), and a
base URL carrying userinfo is refused outright.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_PER_PAGE = 100
MAX_PAGES = 1000


class GitLabApiError(RuntimeError):
    """Raised when the GitLab API cannot be reached or returns an unusable body."""


class GitLabClient:
    """Minimal authenticated read client for one GitLab instance."""

    def __init__(
        self,
        base_url: str,
        auth_token: str,
        *,
        allow_insecure: bool = False,
        per_page: int = DEFAULT_PER_PAGE,
        timeout: float = 15.0,
        opener=None,
    ) -> None:
        if not isinstance(auth_token, str) or not auth_token.strip():
            raise GitLabApiError("a GitLab access token is required")
        if not isinstance(per_page, int) or isinstance(per_page, bool) or not (
            1 <= per_page <= DEFAULT_PER_PAGE
        ):
            raise GitLabApiError(
                f"per_page must be an integer in 1..{DEFAULT_PER_PAGE}"
            )
        parsed = urllib.parse.urlsplit(base_url if isinstance(base_url, str) else "")
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise GitLabApiError("base_url must be an absolute http(s) URL")
        if "@" in parsed.netloc:
            raise GitLabApiError("base_url must not carry credentials")
        if parsed.query or parsed.fragment or parsed.path not in ("", "/"):
            raise GitLabApiError("base_url must be an origin with no path or query")
        if parsed.scheme == "http" and not allow_insecure:
            raise GitLabApiError(
                "refusing to send an access token over plain HTTP; pass "
                "allow_insecure=True only for a tailnet-only instance"
            )
        self._base = f"{parsed.scheme}://{parsed.netloc}"
        self._token = auth_token.strip()
        self._per_page = per_page
        self._timeout = timeout
        self._open = opener or urllib.request.urlopen

    def _get(self, path: str, params: dict[str, str]) -> tuple[bytes, dict[str, str]]:
        query = urllib.parse.urlencode(params)
        url = f"{self._base}{path}?{query}"
        request = urllib.request.Request(
            url,
            headers={
                "PRIVATE-TOKEN": self._token,
                "Accept": "application/json",
                "User-Agent": "devgate-forge-adapter",
            },
            method="GET",
        )
        try:
            with self._open(request, timeout=self._timeout) as response:
                body = response.read()
                headers = {k.lower(): v for k, v in response.headers.items()}
                return body, headers
        except (urllib.error.URLError, OSError) as e:
            # The request object holds the token; never interpolate it here.
            raise GitLabApiError(f"GitLab request failed for {path}: {e}") from e

    def list_projects(self, *, membership: bool = True) -> list[dict]:
        """Walk every project the token can see, following X-Next-Page."""
        projects: list[dict] = []
        page = 1
        while page <= MAX_PAGES:
            params = {
                "membership": "true" if membership else "false",
                "per_page": str(self._per_page),
                "page": str(page),
                "order_by": "id",
                "sort": "asc",
            }
            body, headers = self._get("/api/v4/projects", params)
            try:
                chunk = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                raise GitLabApiError(
                    f"GitLab returned a non-JSON project list on page {page}"
                ) from e
            if not isinstance(chunk, list):
                raise GitLabApiError(
                    f"GitLab project list on page {page} is not an array"
                )
            for item in chunk:
                if isinstance(item, dict):
                    projects.append(item)
            next_page = (headers.get("x-next-page") or "").strip()
            if not next_page:
                return projects
            try:
                page = int(next_page)
            except ValueError as e:
                raise GitLabApiError(
                    f"GitLab returned an unusable X-Next-Page: {next_page!r}"
                ) from e
            if page <= 0:
                raise GitLabApiError("GitLab returned a non-positive next page")
        raise GitLabApiError(f"GitLab project walk exceeded {MAX_PAGES} pages")

    def project_urls(self, *, membership: bool = True) -> list[str]:
        """Return non-archived project web URLs, sorted and deduplicated."""
        urls = set()
        for project in self.list_projects(membership=membership):
            if project.get("archived"):
                continue
            url = project.get("web_url")
            if isinstance(url, str) and url.strip():
                urls.add(url.strip())
        return sorted(urls)
