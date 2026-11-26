# // spec: GLF-02, GLF-11
"""hub.forge.adapter — ForgeAdapter implementations for GitHub and GitLab.

Provides constant-time webhook authentication, normalized PR/MR diff context
extraction, pipeline/commit status reporting payloads, and runner enrollment
metadata tagging without leaking secrets.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Protocol


class ForgeError(ValueError):
    """Raised when forge payload or configuration is malformed."""


class ForgeAuthError(PermissionError):
    """Raised when webhook authentication fails."""


@dataclass(frozen=True)
class DiffContext:
    """Forge-neutral representation of a PR or MR diff event."""

    forge: str
    repository: str
    change_id: int
    base_ref: str
    head_sha: str
    changed_files: tuple[str, ...]


@dataclass(frozen=True)
class GateStatusReport:
    """Forge-neutral gate verdict mapped to a forge-specific status payload."""

    forge: str
    endpoint: str
    state: str
    context: str
    description: str
    payload: dict


class ForgeAdapter(Protocol):
    """Protocol implemented by GitHub and GitLab forge adapters (GLF-02)."""

    forge_name: str

    def verify_webhook(self, headers: dict[str, str], body: bytes, secret: str) -> bool:
        """Constant-time verification of forge webhook signature/token."""

    def extract_diff_context(self, event_payload: dict) -> DiffContext:
        """Normalize a PR/MR webhook payload into a DiffContext."""

    def build_status_report(
        self,
        repository: str,
        sha: str,
        gate_name: str,
        passed: bool,
        description: str,
    ) -> GateStatusReport:
        """Build the forge API status report for a gate decision."""


def _header_lookup(headers: dict[str, str], target_lower: str) -> str:
    for key, value in headers.items():
        if isinstance(key, str) and key.lower() == target_lower:
            return value if isinstance(value, str) else ""
    return ""


class GitHubForgeAdapter:
    """GitHub webhook, PR diff, and commit status adapter."""

    forge_name = "github"

    def verify_webhook(self, headers: dict[str, str], body: bytes, secret: str) -> bool:
        if not secret or not isinstance(body, (bytes, bytearray)):
            raise ForgeAuthError("github webhook secret and raw body required")
        sig = _header_lookup(headers, "x-hub-signature-256")
        if not sig.startswith("sha256="):
            raise ForgeAuthError("missing or malformed X-Hub-Signature-256 header")
        expected = "sha256=" + hmac.new(
            secret.encode("utf-8"), bytes(body), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ForgeAuthError("github webhook signature mismatch")
        return True

    def extract_diff_context(self, event_payload: dict) -> DiffContext:
        if not isinstance(event_payload, dict):
            raise ForgeError("event_payload must be a dict")
        pr = event_payload.get("pull_request") if "pull_request" in event_payload else None
        repo = event_payload.get("repository") if "repository" in event_payload else None
        if not isinstance(pr, dict) or not isinstance(repo, dict):
            raise ForgeError("github payload missing pull_request or repository object")
        full_name = repo.get("full_name") if "full_name" in repo else ""
        number = pr.get("number") if "number" in pr else 0
        base = pr.get("base") if "base" in pr else None
        head = pr.get("head") if "head" in pr else None
        if not isinstance(base, dict) or not isinstance(head, dict):
            raise ForgeError("github pull_request missing base or head")
        base_ref = base.get("ref") if "ref" in base else ""
        head_sha = head.get("sha") if "sha" in head else ""
        files = event_payload.get("changed_files") if "changed_files" in event_payload else []
        if not isinstance(full_name, str) or not full_name or not isinstance(head_sha, str) or not head_sha:
            raise ForgeError("github payload missing repository full_name or head sha")
        file_tuple = tuple(str(f) for f in files) if isinstance(files, list) else ()
        return DiffContext(
            forge="github",
            repository=full_name,
            change_id=int(number) if isinstance(number, int) else 0,
            base_ref=str(base_ref or "main"),
            head_sha=head_sha,
            changed_files=file_tuple,
        )

    def build_status_report(
        self,
        repository: str,
        sha: str,
        gate_name: str,
        passed: bool,
        description: str,
    ) -> GateStatusReport:
        state = "success" if passed else "failure"
        endpoint = f"/repos/{repository}/statuses/{sha}"
        payload = {
            "state": state,
            "context": f"devgate/{gate_name}",
            "description": description[:140],
        }
        return GateStatusReport(
            forge="github",
            endpoint=endpoint,
            state=state,
            context=f"devgate/{gate_name}",
            description=description[:140],
            payload=payload,
        )


class GitLabForgeAdapter:
    """GitLab CE/EE webhook, MR diff, and pipeline commit status adapter (GLF-02)."""

    forge_name = "gitlab"

    def verify_webhook(self, headers: dict[str, str], body: bytes, secret: str) -> bool:
        if not secret or not isinstance(body, (bytes, bytearray)):
            raise ForgeAuthError("gitlab webhook secret and raw body required")
        token = _header_lookup(headers, "x-gitlab-token")
        if not token:
            raise ForgeAuthError("missing X-Gitlab-Token header")
        if not hmac.compare_digest(token.encode("utf-8"), secret.encode("utf-8")):
            raise ForgeAuthError("gitlab webhook token mismatch")
        return True

    def extract_diff_context(self, event_payload: dict) -> DiffContext:
        if not isinstance(event_payload, dict):
            raise ForgeError("event_payload must be a dict")
        project = event_payload.get("project") if "project" in event_payload else None
        attrs = (
            event_payload.get("object_attributes")
            if "object_attributes" in event_payload
            else None
        )
        if not isinstance(project, dict) or not isinstance(attrs, dict):
            raise ForgeError("gitlab payload missing project or object_attributes")
        path_with_ns = (
            project.get("path_with_namespace") if "path_with_namespace" in project else ""
        )
        iid = attrs.get("iid") if "iid" in attrs else 0
        target_branch = attrs.get("target_branch") if "target_branch" in attrs else "main"
        last_commit = attrs.get("last_commit") if "last_commit" in attrs else None
        head_sha = ""
        if isinstance(last_commit, dict) and "id" in last_commit:
            head_sha = str(last_commit["id"] or "")
        elif "last_commit_sha" in attrs:
            head_sha = str(attrs["last_commit_sha"] or "")
        if not isinstance(path_with_ns, str) or not path_with_ns or not head_sha:
            raise ForgeError("gitlab payload missing path_with_namespace or commit sha")
        files = event_payload.get("changed_files") if "changed_files" in event_payload else []
        file_tuple = tuple(str(f) for f in files) if isinstance(files, list) else ()
        return DiffContext(
            forge="gitlab",
            repository=path_with_ns,
            change_id=int(iid) if isinstance(iid, int) else 0,
            base_ref=str(target_branch or "main"),
            head_sha=head_sha,
            changed_files=file_tuple,
        )

    def build_status_report(
        self,
        repository: str,
        sha: str,
        gate_name: str,
        passed: bool,
        description: str,
    ) -> GateStatusReport:
        state = "success" if passed else "failed"
        encoded_repo = repository.replace("/", "%2F")
        endpoint = f"/api/v4/projects/{encoded_repo}/statuses/{sha}"
        payload = {
            "state": state,
            "name": f"devgate/{gate_name}",
            "description": description[:140],
        }
        return GateStatusReport(
            forge="gitlab",
            endpoint=endpoint,
            state=state,
            context=f"devgate/{gate_name}",
            description=description[:140],
            payload=payload,
        )


def get_forge_adapter(forge: str) -> ForgeAdapter:
    """Return the adapter for 'github' or 'gitlab', failing closed on unknown forges."""
    if forge == "github":
        return GitHubForgeAdapter()
    if forge == "gitlab":
        return GitLabForgeAdapter()
    raise ForgeError(f"unsupported forge: {forge!r}")
