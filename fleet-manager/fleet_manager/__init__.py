# spec: repo-003-01, fleet-001-01, fleet-001-02, fleet-001-03
"""Fleet Manager package (product-tiers boundary root, REPO-002).

Everything here is inside the `fleet-manager/` boundary declared by
`fleet-manager/manifest.json`. Open-core code must not import this package; the
direction is one-way and `scripts/check_boundary.py` enforces it in CI.

Two unnamed subsystems are kept apart on purpose: `model` is desired state (the
manager's), `observation` is what a host reports. They do not import each other.
"""

from .contracts import (  # noqa: F401
    CONTRACT_VERSION,
    ContractError,
    ContractInvalid,
    ContractUnsupportedVersion,
    build_capacity_decision,
    build_receipt,
    check_version,
    describe,
    load_schema,
    parse,
    validate,
)
from .documents import (  # noqa: F401
    DOCUMENT_SCHEMA,
    from_document,
    to_document,
)
from .model import (  # noqa: F401
    Assignment,
    AssignmentState,
    Capacity,
    DesiredState,
    DisruptionBudget,
    Drain,
    DrainState,
    Host,
    HostState,
    ModelError,
    Pool,
    Repository,
    Rollout,
    RolloutState,
    Runtime,
    TrustClass,
)
from .observation import (  # noqa: F401
    Observation,
    ObservationError,
    ObservedRunner,
)

__all__ = [
    "CONTRACT_VERSION",
    "ContractError",
    "ContractInvalid",
    "ContractUnsupportedVersion",
    "build_capacity_decision",
    "build_receipt",
    "check_version",
    "describe",
    "load_schema",
    "parse",
    "validate",
    "Assignment",
    "AssignmentState",
    "Capacity",
    "DesiredState",
    "DisruptionBudget",
    "Drain",
    "DrainState",
    "Host",
    "HostState",
    "ModelError",
    "Pool",
    "Repository",
    "Rollout",
    "RolloutState",
    "Runtime",
    "TrustClass",
    "DOCUMENT_SCHEMA",
    "from_document",
    "to_document",
    "Observation",
    "ObservationError",
    "ObservedRunner",
]
