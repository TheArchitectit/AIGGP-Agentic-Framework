# // spec: GLF-10, GLF-13
"""hub.forge.fleet — merge GitLab sources into the fleet scan declaration.

`scripts/secret-scan-declared.sh` already derives the GitHub half from
`gh repo list`. This module derives the GitLab half from declared instances and
merges both into the one-URL-per-line declaration `scripts/secret-scan-fleet.sh`
consumes.

Two fail-closed rules, matching the generator's own:

  * an undeclared instance is refused by name, never silently skipped
    (GLF-13: a GitLab surface is opt-in); and
  * an empty merged declaration is an error, because a sweep that scans
    nothing and reports clean is the failure the declaration walk exists to
    prevent.

The walk is performed by injected clients (`hub.forge.api.GitLabClient` in
production, a fake in tests), so no instance is contacted to exercise it.
"""

from __future__ import annotations

from .deployment import declared_gitlab_instances
from .instance import InstanceDeclaration


class FleetDeclarationError(ValueError):
    """Raised when the fleet declaration cannot be built fail-closed."""


def normalize_url(url: str) -> str:
    """Normalize a repository URL for deduplication, preserving its spelling."""
    return (url or "").strip().rstrip("/").removesuffix(".git")


def walk_gitlab_sources(
    declarations: dict[str, InstanceDeclaration],
    clients: dict[str, object],
) -> list[str]:
    """Return project URLs for every declared GitLab instance.

    `clients` maps instance_id to an object with `project_urls()`. A client for
    an undeclared instance is refused, and a declared instance with no client
    is an error: both would otherwise produce a shorter declaration that reads
    as a clean fleet.
    """
    declared = set(declared_gitlab_instances(declarations))
    undeclared = sorted(set(clients) - declared)
    if undeclared:
        raise FleetDeclarationError(
            f"undeclared GitLab instance(s) refused: {undeclared} (GLF-13)"
        )
    missing = sorted(declared - set(clients))
    if missing:
        raise FleetDeclarationError(
            f"declared GitLab instance(s) have no walk client: {missing}; a "
            f"declared instance that is not walked shortens the sweep silently"
        )
    urls: list[str] = []
    for instance_id in sorted(declared):
        client = clients[instance_id]
        project_urls = getattr(client, "project_urls", None)
        if not callable(project_urls):
            raise FleetDeclarationError(
                f"walk client for {instance_id!r} has no project_urls()"
            )
        found = project_urls()
        if not isinstance(found, list):
            raise FleetDeclarationError(
                f"walk client for {instance_id!r} returned a non-list"
            )
        for url in found:
            normalized = normalize_url(str(url))
            if normalized:
                urls.append(normalized)
    return sorted(set(urls), key=lambda u: (u.lower(), u))


def build_fleet_declaration(
    github_urls: list[str],
    declarations: dict[str, InstanceDeclaration],
    clients: dict[str, object],
) -> list[str]:
    """Merge GitHub and GitLab sources into a sorted, deduplicated declaration."""
    combined = {normalize_url(u) for u in github_urls if normalize_url(u)}
    combined.update(walk_gitlab_sources(declarations, clients))
    if not combined:
        raise FleetDeclarationError(
            "the merged declaration is empty: a sweep of nothing is not a "
            "clean fleet"
        )
    return sorted(combined, key=lambda u: (u.lower(), u))


def render_declaration(urls: list[str]) -> str:
    """Render the declaration file body (one URL per line, trailing newline)."""
    if not urls:
        raise FleetDeclarationError("refusing to render an empty declaration")
    return "\n".join(urls) + "\n"
