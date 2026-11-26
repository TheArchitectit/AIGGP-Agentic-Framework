# // spec: GLF-10, GLF-13
"""hub.forge.deployment — deployer-supplied GitLab instance declarations.

Per-instance ownership, cadence and supported-version data live in deployer
configuration (`hub/forge/instances.toml`, override with
`FORGE_INSTANCES_CONFIG`), never in code (GLF-13). The shipped file declares
nothing, so a fresh deployment has no GitLab surface at all: an undeclared
instance is refused by name, and GitLab.com is enabled only by an explicit
`surface = "hosted"` declaration for `gitlab.com`.

This module parses and validates that file and is the single place an adapter
is bound to an instance. It never contacts an instance; the API client lives
in `hub.forge.api`.
"""

from __future__ import annotations

import os
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - CI runs 3.12
    import tomli as tomllib  # type: ignore[no-redef]

from .adapter import ForgeAdapter, get_forge_adapter
from .instance import (
    HOSTED_GITLAB_INSTANCE_ID,
    InstanceDeclaration,
    OwnershipValidationError,
    validate_instance_declaration,
)

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "instances.toml"
CONFIG_ENV = "FORGE_INSTANCES_CONFIG"
CONFIG_VERSION = 1

_REQUIRED = (
    "instance_id",
    "forge",
    "host_alias",
    "service_name",
    "owner",
    "backup_path",
    "runner_scope",
    "default_visibility",
    "tls_valid",
    "security_patch_cadence_days",
    "upgrade_cadence_days",
    "supported_version",
)
_OPTIONAL = ("surface", "ip_repo_visibilities")


class DeploymentConfigError(ValueError):
    """Raised when the deployer instance configuration is malformed."""


def _declaration_from_mapping(raw: object, where: str) -> InstanceDeclaration:
    if not isinstance(raw, dict):
        raise DeploymentConfigError(f"{where}: each [[instance]] must be a table")
    unknown = sorted(set(raw) - set(_REQUIRED) - set(_OPTIONAL))
    if unknown:
        raise DeploymentConfigError(f"{where}: unknown field(s) {unknown}")
    missing = sorted(set(_REQUIRED) - set(raw))
    if missing:
        raise DeploymentConfigError(f"{where}: missing required field(s) {missing}")
    vis = raw.get("ip_repo_visibilities", {})
    if not isinstance(vis, dict):
        raise DeploymentConfigError(
            f"{where}: ip_repo_visibilities must be a table of repo = visibility"
        )
    return InstanceDeclaration(
        instance_id=str(raw["instance_id"]),
        forge=str(raw["forge"]),
        host_alias=str(raw["host_alias"]),
        service_name=str(raw["service_name"]),
        owner=str(raw["owner"]),
        backup_path=str(raw["backup_path"]),
        runner_scope=str(raw["runner_scope"]),
        default_visibility=str(raw["default_visibility"]),
        ip_repo_visibilities={str(k): str(v) for k, v in vis.items()},
        tls_valid=raw["tls_valid"],  # type: ignore[arg-type]
        security_patch_cadence_days=raw["security_patch_cadence_days"],  # type: ignore[arg-type]
        upgrade_cadence_days=raw["upgrade_cadence_days"],  # type: ignore[arg-type]
        supported_version=str(raw["supported_version"]),
        surface=str(raw.get("surface", "self-hosted")),
    )


def config_path(path: str | os.PathLike | None = None) -> Path:
    """Resolve the deployer config path: argument, then env, then shipped file."""
    if path is not None:
        return Path(path)
    env = os.environ.get(CONFIG_ENV)
    return Path(env) if env else DEFAULT_CONFIG_PATH


def load_instance_declarations(
    path: str | os.PathLike | None = None,
) -> dict[str, InstanceDeclaration]:
    """Load and validate declarations, keyed by instance_id.

    A missing explicitly-named file is an error. The shipped default file is
    allowed to be absent and then declares nothing (GitLab off by default), so
    a fresh checkout needs no deployment data to import this module.
    """
    explicit = path is not None or CONFIG_ENV in os.environ
    p = config_path(path)
    if not p.is_file():
        if explicit:
            raise DeploymentConfigError(f"instance config not found: {p}")
        return {}
    try:
        with p.open("rb") as fh:
            doc = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise DeploymentConfigError(f"cannot read instance config {p}: {e}") from e
    if not isinstance(doc, dict):
        raise DeploymentConfigError(f"{p}: top level must be a table")
    version = doc.get("version", CONFIG_VERSION)
    if version != CONFIG_VERSION:
        raise DeploymentConfigError(
            f"{p}: unsupported config version {version!r} (expected {CONFIG_VERSION})"
        )
    entries = doc.get("instance", [])
    if not isinstance(entries, list):
        raise DeploymentConfigError(f"{p}: [[instance]] must be an array of tables")

    out: dict[str, InstanceDeclaration] = {}
    for index, raw in enumerate(entries):
        decl = _declaration_from_mapping(raw, f"{p}: instance[{index}]")
        if decl.instance_id in out:
            raise DeploymentConfigError(
                f"{p}: duplicate instance_id {decl.instance_id!r}"
            )
        try:
            validate_instance_declaration(decl)
        except OwnershipValidationError as e:
            raise DeploymentConfigError(f"{p}: {e}") from e
        out[decl.instance_id] = decl
    return out


def declared_gitlab_instances(
    declarations: dict[str, InstanceDeclaration],
) -> list[str]:
    """Return the declared GitLab instance ids, sorted."""
    return sorted(
        iid for iid, d in declarations.items() if d.forge == "gitlab"
    )


def hosted_surface_enabled(declarations: dict[str, InstanceDeclaration]) -> bool:
    """True only when a declaration explicitly opts in to GitLab.com (GLF-13)."""
    return HOSTED_GITLAB_INSTANCE_ID in declarations and (
        declarations[HOSTED_GITLAB_INSTANCE_ID].surface == "hosted"
    )


def resolve_instance_adapter(
    forge: str,
    instance_id: str | None,
    declarations: dict[str, InstanceDeclaration],
) -> ForgeAdapter:
    """Bind an adapter to a declared instance, refusing anything undeclared.

    GitHub needs no declaration here: self-hosted GitHub runners are the
    existing fleet. A GitLab surface is opt-in, so an undeclared instance is
    refused by name, and GitLab.com is reachable only through an explicit
    hosted declaration.
    """
    if forge == "github":
        return get_forge_adapter("github")
    if forge != "gitlab":
        return get_forge_adapter(forge)  # raises ForgeError on unknown forges
    if not instance_id:
        raise OwnershipValidationError(
            "a GitLab adapter must be bound to a declared instance (GLF-13)"
        )
    decl = declarations.get(instance_id)
    if decl is None:
        raise OwnershipValidationError(
            f"instance {instance_id!r} has no ownership/cadence declaration in "
            f"deployer configuration; GitLab surfaces are opt-in and "
            f"{HOSTED_GITLAB_INSTANCE_ID!r} stays off unless declared (GLF-13)"
        )
    validate_instance_declaration(decl)
    return get_forge_adapter("gitlab")
