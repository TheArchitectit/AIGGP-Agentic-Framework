# spec: repo-003-01, fleet-001-01, fleet-001-02, fleet-001-03, fleet-002-01, fleet-002-02, fleet-002-03, fleet-002-04, fleet-003-01, fleet-003-02, fleet-003-03, fleet-003-04, fleet-004-01, fleet-004-02, fleet-004-03, fleet-004-04, fleet-004-05, fleet-005-01, fleet-005-02, fleet-005-03, fleet-005-04, fleet-005-05, fleet-006-01, fleet-006-02, fleet-006-03, fleet-006-04
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
`reconcile` reads the other side: it diffs a revision against what hosts report
and returns a bounded diff whose changes are the same values `plan` takes, so a
reconciliation is carried out through the same apply as an operator's plan.
`channel` is the other direction of trust: how a host agent proves it is the
host it claims to be when it calls in. It holds enrollment, rotation, and
revocation as values and the signed-report checks as rules, with the signature
provider injected — the manager never dials a host (FLEET-004), and choosing a
verifier stays a decision with a security sign-off rather than a default in a
module.
`operations` is what such a caller may be told to do: a closed catalogue of
typed adapter operations (no shell-shaped parameter exists to say "run this"),
a deny-by-default allowlist per agent, and receipts — the agent's claim is
evidence tied to an operation the manager issued, and the manager's contract-v1
receipt is built from that claim rather than forwarded (FLEET-005).
`state` is the same boundary seen from the host's side: the manager signs a
desired state for exactly one audience, at a revision, with a bounded lifetime
and a monotonic per-audience sequence, over one frozen canonical profile. A host
verifies it before reconciling toward it, and the sequence is what makes "this
state" mean now rather than whenever it was captured (FLEET-006).
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
from .channel import (  # noqa: F401
    CHANNEL_SCHEMA,
    MAX_BODY_BYTES,
    MAX_CLOCK_SKEW,
    MAX_MESSAGE_LIFETIME,
    ROTATION_OVERLAP,
    AcceptedReport,
    AgentChannel,
    ChannelEnvelope,
    ChannelError,
    CredentialStatus,
    EnrollmentToken,
    HostCredential,
    envelope_from_document,
    envelope_to_document,
    key_id_for,
    signed_bytes,
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
from .operations import (  # noqa: F401
    OPERATION_SCHEMA,
    READ_ONLY,
    RECEIPT_SCHEMA,
    RUNNER_ENROLL_MIGRATION,
    AgentCapabilities,
    AgentReceipt,
    Evidence,
    Operation,
    OperationKind,
    OperationLedger,
    OperationRefused,
    ReceiptOutcome,
    Subject,
    SubjectKind,
    permit,
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
from .reconcile import (  # noqa: F401
    ConvergenceLimits,
    Deferred,
    Drift,
    DriftKind,
    ReconcileError,
    Reconciliation,
    bound_candidates,
    observation_from_document,
    observation_to_document,
    reconcile,
    reconciliation_id_for,
)
# `signed_bytes` is deliberately not re-exported: `channel` already puts that
# name in this namespace, for the report profile, and two meanings under one
# name is how a signature gets verified over the wrong bytes. Import
# `fleet_manager.state.signed_bytes` when you mean the desired-state profile.
from .state import (  # noqa: F401
    MAX_STATE_LIFETIME,
    STATE_SCHEMA,
    AcceptedState,
    SignedState,
    StateError,
    StateIssuer,
    accept_state,
    state_from_document,
    state_to_document,
)

__all__ = [
    "CHANNEL_SCHEMA",
    "MAX_BODY_BYTES",
    "MAX_CLOCK_SKEW",
    "MAX_MESSAGE_LIFETIME",
    "ROTATION_OVERLAP",
    "AcceptedReport",
    "AgentChannel",
    "ChannelEnvelope",
    "ChannelError",
    "CredentialStatus",
    "EnrollmentToken",
    "HostCredential",
    "envelope_from_document",
    "envelope_to_document",
    "key_id_for",
    "signed_bytes",
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
    "OPERATION_SCHEMA",
    "READ_ONLY",
    "RECEIPT_SCHEMA",
    "RUNNER_ENROLL_MIGRATION",
    "AgentCapabilities",
    "AgentReceipt",
    "Evidence",
    "Operation",
    "OperationKind",
    "OperationLedger",
    "OperationRefused",
    "ReceiptOutcome",
    "Subject",
    "SubjectKind",
    "permit",
    "ConvergenceLimits",
    "Deferred",
    "Drift",
    "DriftKind",
    "ReconcileError",
    "Reconciliation",
    "bound_candidates",
    "observation_from_document",
    "observation_to_document",
    "reconcile",
    "reconciliation_id_for",
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
    "MAX_STATE_LIFETIME",
    "STATE_SCHEMA",
    "AcceptedState",
    "SignedState",
    "StateError",
    "StateIssuer",
    "accept_state",
    "state_from_document",
    "state_to_document",
]
