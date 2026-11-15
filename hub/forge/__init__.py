# // spec: GLF-01, GLF-02, GLF-03, GLF-10, GLF-11, GLF-12, GLF-13
"""hub.forge — forge-neutral adapter, deployment config, and parity drill.

Supports both GitHub and self-hosted GitLab CE/EE forges across:
- Webhook signature/token verification (GLF-02)
- Merge-request / pull-request diff context normalization (GLF-02)
- Pipeline / commit status reporting (GLF-02)
- Reusable CI template mirror verification (GLF-01)
- Self-hosted instance discovery & backup/restore drill validation (GLF-10)
- Runner enrollment forge tagging & digest-pin enforcement (GLF-11, GLF-12)
- Per-instance ownership & access-model validation (GLF-13)
- Deployer-supplied instance declarations and opt-in GitLab.com (GLF-13)
- Authenticated GitLab API reads and the fleet-source walk (GLF-02, GLF-13)
- Seeded violation corpus parity drill across both forge paths (GLF-01, GLF-03)
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
from .api import GitLabApiError, GitLabClient
from .deployment import (
    DEFAULT_CONFIG_PATH,
    DeploymentConfigError,
    config_path,
    declared_gitlab_instances,
    hosted_surface_enabled,
    load_instance_declarations,
    resolve_instance_adapter,
)
from .fleet import (
    FleetDeclarationError,
    build_fleet_declaration,
    normalize_url,
    render_declaration,
    walk_gitlab_sources,
)
from .instance import (
    HOSTED_GITLAB_INSTANCE_ID,
    BackupDrillReport,
    InstanceDeclaration,
    OwnershipValidationError,
    RunnerImageError,
    validate_backup_restore_drill,
    validate_instance_declaration,
    validate_runner_image_pin,
    verify_gitlab_ci_template_mirrors,
)
from .monitor import audit_deployment
from .parity import (
    GateSeed,
    ParityDivergence,
    ParityDrillError,
    ParityDrillResult,
    corpus_digest,
    corpus_lock,
    run_forge_parity_drill,
    seeded_corpus,
    verify_corpus_pin,
)

__all__ = [
    "BackupDrillReport",
    "DEFAULT_CONFIG_PATH",
    "DeploymentConfigError",
    "DiffContext",
    "FleetDeclarationError",
    "ForgeAdapter",
    "ForgeAuthError",
    "ForgeError",
    "GateSeed",
    "GateStatusReport",
    "GitHubForgeAdapter",
    "GitLabApiError",
    "GitLabClient",
    "GitLabForgeAdapter",
    "HOSTED_GITLAB_INSTANCE_ID",
    "InstanceDeclaration",
    "OwnershipValidationError",
    "ParityDivergence",
    "ParityDrillError",
    "ParityDrillResult",
    "RunnerImageError",
    "audit_deployment",
    "build_fleet_declaration",
    "config_path",
    "corpus_digest",
    "corpus_lock",
    "declared_gitlab_instances",
    "get_forge_adapter",
    "hosted_surface_enabled",
    "load_instance_declarations",
    "normalize_url",
    "render_declaration",
    "resolve_instance_adapter",
    "run_forge_parity_drill",
    "seeded_corpus",
    "validate_backup_restore_drill",
    "validate_instance_declaration",
    "validate_runner_image_pin",
    "verify_corpus_pin",
    "verify_gitlab_ci_template_mirrors",
    "walk_gitlab_sources",
]
