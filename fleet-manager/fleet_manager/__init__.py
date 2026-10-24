# spec: repo-003-01, fleet-001-01, fleet-001-02, fleet-001-03, fleet-002-01, fleet-002-02, fleet-002-03, fleet-002-04
"""Fleet Manager package (product-tiers boundary root, REPO-002).

Everything here is inside the `fleet-manager/` boundary declared by
`fleet-manager/manifest.json`. Open-core code must not import this package; the
direction is one-way and `scripts/check_boundary.py` enforces it in CI.

Two unnamed subsystems are kept apart on purpose: `model` is desired state (the
manager's), `observation` is what a host reports. They do not import each other.

The operation path is `plan` → `apply`: a plan is a prediction (deterministic,
checksummed, capacity-impacted), an apply is the one thing that produces a new
revision, and it does so only against the revision it was planned against, only
for an authorized principal, and only once per idempotency key. `audit` records
both the applies and the refusals; `auth` is where a request becomes a decision.
"""

from .apply import (  # noqa: F401
    ApplyError,
    ApplyRefused,
    ApplyResult,
    IdempotencyLedger,
    apply_plan,
)
from .audit import (  # noqa: F401
    AuditError,
    AuditEvent,
    AuditLog,
    Outcome,
)
from .auth import (  # noqa: F401
    AuthorizationError,
    Principal,
    PrincipalKind,
    Scope,
)
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
from .plan import (  # noqa: F401
    PLAN_CLOCK_FLOOR,
    CapacityImpact,
    Change,
    ChangeKind,
    Plan,
    PlanError,
    build_plan,
    plan_clock,
    plan_id_for,
    simulate,
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
    "ApplyError",
    "ApplyRefused",
    "ApplyResult",
    "IdempotencyLedger",
    "apply_plan",
    "AuditError",
    "AuditEvent",
    "AuditLog",
    "Outcome",
    "AuthorizationError",
    "Principal",
    "PrincipalKind",
    "Scope",
    "PLAN_CLOCK_FLOOR",
    "CapacityImpact",
    "Change",
    "ChangeKind",
    "Plan",
    "PlanError",
    "build_plan",
    "plan_clock",
    "plan_id_for",
    "simulate",
]
