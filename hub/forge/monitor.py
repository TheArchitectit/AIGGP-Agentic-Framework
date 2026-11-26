# // spec: GLF-10, GLF-13
"""hub.forge.monitor — declaration-level health for forge instances.

Live probing of a GitLab instance (TLS handshake, version endpoint, backup
freshness) is not implemented here: there is no instance to probe until
Sprint 0 closes. What this module audits is the part decidable from deployer
configuration and recorded drill reports:

  * each GitLab declaration is complete (owner, cadence, supported version);
  * a matching backup/restore drill report validates (GLF-10);
  * GitLab.com is reported as enabled only when a hosted declaration says so;
  * a requested instance with no declaration is refused by name (GLF-13).

Callers render `audit_deployment()`; a non-empty `findings` list is a
non-green deployment.
"""

from __future__ import annotations

from .deployment import declared_gitlab_instances, hosted_surface_enabled
from .instance import (
    BackupDrillReport,
    InstanceDeclaration,
    OwnershipValidationError,
    validate_backup_restore_drill,
    validate_instance_declaration,
)


def audit_deployment(
    declarations: dict[str, InstanceDeclaration],
    drill_reports: list[BackupDrillReport] | None = None,
    requested: list[str] | None = None,
) -> dict:
    """Return per-instance status plus a findings list for a deployment."""
    reports = {r.instance_id: r for r in (drill_reports or [])}
    findings: list[dict] = []
    statuses: list[dict] = []

    for instance_id in declared_gitlab_instances(declarations):
        decl = declarations[instance_id]
        declared_ok = True
        try:
            validate_instance_declaration(decl)
        except OwnershipValidationError as e:
            declared_ok = False
            findings.append(
                {"instance_id": instance_id, "rule": "GLF-13", "problem": str(e)}
            )
        report = reports.get(instance_id)
        drill_ok = False
        if report is None:
            findings.append(
                {
                    "instance_id": instance_id,
                    "rule": "GLF-10",
                    "problem": "no backup/restore drill report recorded",
                }
            )
        else:
            try:
                drill_ok = validate_backup_restore_drill(report)
            except ValueError as e:
                findings.append(
                    {"instance_id": instance_id, "rule": "GLF-10", "problem": str(e)}
                )
        statuses.append(
            {
                "instance_id": instance_id,
                "owner": decl.owner,
                "surface": decl.surface,
                "declared": declared_ok,
                "backup_drill_evidenced": drill_ok,
            }
        )

    for instance_id in sorted(set(requested or ()) - set(declarations)):
        findings.append(
            {
                "instance_id": instance_id,
                "rule": "GLF-13",
                "problem": (
                    "requested instance is not declared in deployer "
                    "configuration; GitLab surfaces are opt-in"
                ),
            }
        )

    return {
        "instances": statuses,
        "hosted_surface_enabled": hosted_surface_enabled(declarations),
        "findings": findings,
        "green": not findings,
    }
