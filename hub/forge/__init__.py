# // spec: GLF-01, GLF-02, GLF-03, GLF-10, GLF-11, GLF-12, GLF-13
"""hub.forge — Forge-neutral adapter, instance/runner validation, and parity drill.

Supports both GitHub and self-hosted GitLab CE/EE forges across:
- Webhook signature/token verification (GLF-02)
- Merge-request / pull-request diff context normalization (GLF-02)
- Pipeline / commit status reporting (GLF-02)
- Reusable CI template mirror verification (GLF-01)
- Self-hosted instance discovery & backup/restore drill validation (GLF-10)
- Runner enrollment forge tagging & digest-pin enforcement (GLF-11, GLF-12)
- Per-instance ownership & access-model validation (GLF-13)
- Seeded violation corpus parity drill across GitHub and GitLab (GLF-03)
"""

from .adapter import (
    DiffContext,
    ForgeAdapter,
    ForgeAuthError,
    ForgeError,
    GateStatusReport,
    GitHubForgeAdapter,
    GitLabForgeAdapter,
    get_forge_adapter,
)
from .instance import (
    BackupDrillReport,
    InstanceDeclaration,
    OwnershipValidationError,
    RunnerImageError,
    validate_backup_restore_drill,
    validate_instance_declaration,
    validate_runner_image_pin,
    verify_gitlab_ci_template_mirrors,
)
from .parity import (
    ParityCase,
    ParityDrillResult,
    default_seeded_corpus,
    run_forge_parity_drill,
)

__all__ = [
    "BackupDrillReport",
    "DiffContext",
    "ForgeAdapter",
    "ForgeAuthError",
    "ForgeError",
    "GateStatusReport",
    "GitHubForgeAdapter",
    "GitLabForgeAdapter",
    "InstanceDeclaration",
    "OwnershipValidationError",
    "ParityCase",
    "ParityDrillResult",
    "RunnerImageError",
    "default_seeded_corpus",
    "get_forge_adapter",
    "run_forge_parity_drill",
    "validate_backup_restore_drill",
    "validate_instance_declaration",
    "validate_runner_image_pin",
    "verify_gitlab_ci_template_mirrors",
]
