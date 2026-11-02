# // spec: GLF-01, GLF-10, GLF-12, GLF-13
"""hub.forge.instance — GitLab instance discovery, backup drill, runner pin,
template mirror verification, and per-instance ownership validation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_DIGEST_PIN_RE = re.compile(r"^[A-Za-z0-9._/-]+@sha256:[0-9a-f]{64}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class OwnershipValidationError(ValueError):
    """Raised when an instance ownership declaration violates GLF-13."""


class RunnerImageError(ValueError):
    """Raised when a runner or CI container image is not digest-pinned (GLF-12)."""


@dataclass(frozen=True)
class InstanceDeclaration:
    """Per-instance ownership and access-model declaration (GLF-10, GLF-13)."""

    instance_id: str
    forge: str
    host_alias: str
    service_name: str
    owner: str
    backup_path: str
    runner_scope: str
    default_visibility: str
    ip_repo_visibilities: dict[str, str]
    tls_valid: bool


@dataclass(frozen=True)
class BackupDrillReport:
    """Backup and restore drill verification record (GLF-10)."""

    instance_id: str
    backup_archive_digest: str
    restored_commit_sha: str
    expected_commit_sha: str
    restored_mr_count: int
    expected_mr_count: int
    restored_variables_digest: str
    expected_variables_digest: str


def validate_runner_image_pin(image_ref: str) -> str:
    """Enforce that a runner or job container image is pinned by @sha256 digest (GLF-12).

    Rejects mutable tags such as ':latest' or ':v17.4.0' without an immutable digest.
    """
    if not isinstance(image_ref, str) or not image_ref.strip():
        raise RunnerImageError("container image reference must be a non-empty string")
    ref = image_ref.strip()
    if not _DIGEST_PIN_RE.match(ref):
        raise RunnerImageError(
            f"mutable or unpinned container image rejected (GLF-12): {ref!r}"
        )
    return ref


def validate_instance_declaration(decl: InstanceDeclaration) -> InstanceDeclaration:
    """Validate self-hosted GitLab instance discovery & ownership rules (GLF-10, GLF-13)."""
    if not isinstance(decl, InstanceDeclaration):
        raise OwnershipValidationError("declaration must be an InstanceDeclaration")
    if decl.forge != "gitlab":
        raise OwnershipValidationError(f"expected gitlab forge, got {decl.forge!r}")
    if not decl.instance_id or not decl.host_alias or not decl.service_name:
        raise OwnershipValidationError(
            "instance_id, host_alias, and service_name are required (GLF-10)"
        )
    if not decl.tls_valid:
        raise OwnershipValidationError(
            f"instance {decl.instance_id!r} must have valid TLS health check (GLF-10)"
        )
    if not decl.owner or not decl.owner.strip():
        raise OwnershipValidationError(
            f"instance {decl.instance_id!r} missing designated owner (GLF-13)"
        )
    if not decl.backup_path or not decl.backup_path.startswith("/"):
        raise OwnershipValidationError(
            f"instance {decl.instance_id!r} missing absolute backup_path (GLF-13)"
        )
    if decl.runner_scope not in ("instance-dedicated", "group-dedicated", "repo-scoped"):
        raise OwnershipValidationError(
            f"instance {decl.instance_id!r} has invalid runner_scope {decl.runner_scope!r} (GLF-13)"
        )
    if decl.default_visibility not in ("private", "internal"):
        raise OwnershipValidationError(
            f"instance {decl.instance_id!r} default_visibility must be private or internal, "
            f"got {decl.default_visibility!r} (GLF-13)"
        )
    for repo_name, vis in (decl.ip_repo_visibilities or {}).items():
        if vis not in ("private", "internal"):
            raise OwnershipValidationError(
                f"intellectual-property repository {repo_name!r} on {decl.instance_id!r} "
                f"cannot have visibility {vis!r}; must be private or internal (GLF-13)"
            )
    return decl


def validate_backup_restore_drill(report: BackupDrillReport) -> bool:
    """Verify that a GitLab backup and scratch restore drill preserves state (GLF-10)."""
    if not isinstance(report, BackupDrillReport):
        raise ValueError("report must be a BackupDrillReport")
    if not report.instance_id:
        raise ValueError("backup drill report missing instance_id")
    if not _SHA256_RE.match(report.backup_archive_digest or ""):
        raise ValueError("backup_archive_digest must be sha256:<64-hex>")
    if not report.expected_commit_sha or report.restored_commit_sha != report.expected_commit_sha:
        raise ValueError("restored repository commit history does not match pre-backup state")
    if report.expected_mr_count < 0 or report.restored_mr_count != report.expected_mr_count:
        raise ValueError("restored merge request metadata count does not match pre-backup state")
    if (
        not _SHA256_RE.match(report.expected_variables_digest or "")
        or report.restored_variables_digest != report.expected_variables_digest
    ):
        raise ValueError("restored CI variables digest does not match pre-backup state")
    return True


def verify_gitlab_ci_template_mirrors(repo_root: Path) -> list[str]:
    """Verify every reusable GitHub workflow template has a digest-pinned GitLab mirror (GLF-01, GLF-12)."""
    root = Path(repo_root)
    gh_dir = root / "templates" / "github-workflows"
    gl_dir = root / "templates" / "gitlab-ci"
    if not gh_dir.is_dir() or not gl_dir.is_dir():
        raise FileNotFoundError("templates/github-workflows and templates/gitlab-ci must exist")
    gh_stems = sorted(p.stem for p in gh_dir.glob("*.yml"))
    if not gh_stems:
        raise ValueError("no github workflow templates found")
    verified: list[str] = []
    for stem in gh_stems:
        mirror = gl_dir / f"{stem}.gitlab-ci.yml"
        if not mirror.is_file():
            raise FileNotFoundError(f"missing GitLab CI mirror for {stem}.yml: {mirror}")
        text = mirror.read_text(encoding="utf-8")
        images = [
            ln.split("image:", 1)[1].strip()
            for ln in text.splitlines()
            if ln.strip().startswith("image:")
        ]
        if not images:
            raise RunnerImageError(f"GitLab CI template {mirror.name} declares no container image")
        for img in images:
            validate_runner_image_pin(img)
        verified.append(mirror.name)
    return verified
