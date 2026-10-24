# spec: fleet-005-01, fleet-005-02, fleet-005-03, fleet-005-04, fleet-005-05
"""What an agent may be told to do, and what proves it did.

Box 3.2 is the other half of the channel. Sprint 3.1 established *who* is
calling; this module establishes *what a call may ask for*, and what comes back
afterwards. Three rules, each one a failure the program names:

1. **No remote shell (D4, R7).** An operation is a closed enum with a closed
   parameter set per kind. There is no field that carries a command, an argv, a
   script, or an environment: those *names* are refused by name wherever they
   appear, so an attempt to smuggle one is a refusal rather than an unread
   parameter. Nothing here can express "run this".
2. **Deny by default.** An agent declares what it has installed — its adapters
   and the operations it may perform — and `permit()` refuses anything not
   declared. `cancel_or_timeout` is refused even when declared unless the
   deployment granted it explicitly; the adapter contract allows cancellation
   "only under explicit policy", and a policy that defaults to yes is not a
   policy.
3. **A receipt is evidence, not authority.** An agent's receipt is a claim tied
   to an operation the manager issued: unknown key, wrong host, a completion
   without an evidence digest, or a second receipt that says something
   different about the same key are all refused. The manager's *authoritative*
   receipt is the contract-v1 document the evidence plane consumes, and it is
   built by the manager from the agent's claim — never forwarded from it.

That last distinction is not pedantry. The v1 `operation_receipt` contract
enumerates control-plane operations (`enroll`, `assign`, `release`, `drain`,
`apply`, `revoke`), while an adapter operation is `ensure_image`,
`create_runner`, `destroy_runner` and so on. They are different vocabularies
for different audiences, so the mapping between them is declared in one dict
(`_CONTRACT_OPERATION`) and tested in both directions rather than left implicit
in a call site.

Secrets: parameters and receipts carry **references**, never values (SEC-001).
`registration_ref` must be `ref:<name>`; any parameter value or receipt detail
that matches a credential shape is refused and **not echoed**, which is the
same rule the audit log applies, reusing its pattern so there is one definition
of "looks like a secret" in this package.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .audit import _SECRET_SHAPED
from .channel import _timestamp
from .contracts import build_receipt
from .model import Runtime, _identifier, _request_id

OPERATION_SCHEMA = "fleet-manager-agent-operation/1"
RECEIPT_SCHEMA = "fleet-manager-agent-receipt/1"

# Names that would turn an operation into a shell. An operation carries typed
# fields only, so any of these is refused wherever it appears.
_SHELL_SHAPED = frozenset({
    "args", "argv", "bash", "cmd", "command", "commands", "entrypoint", "env",
    "environment", "exec", "script", "sh", "shell", "stdin", "stdout",
})

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_REFERENCE = re.compile(r"^ref:[a-z0-9][a-z0-9._-]{0,63}$")
_MAX_VALUE = 512


class OperationRefused(ValueError):
    """An operation or receipt was refused. Names the rule, never a value."""


class OperationKind(str, Enum):
    ENSURE_IMAGE = "ensure_image"
    CREATE_RUNNER = "create_runner"
    MARK_DRAIN = "mark_drain"
    DESTROY_RUNNER = "destroy_runner"
    CANCEL_OR_TIMEOUT = "cancel_or_timeout"
    OBSERVE_RUNNER = "observe_runner"
    PROVE_CLEANUP = "prove_cleanup"
    ROLLBACK_ADAPTER = "rollback_adapter"


class SubjectKind(str, Enum):
    HOST = "host"
    POOL = "pool"
    RUNNER = "runner"


class ReceiptOutcome(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


# Operations that change nothing. They are permitted (an agent has to observe),
# but they cannot be receipted: there is nothing to attest.
READ_ONLY = frozenset({OperationKind.OBSERVE_RUNNER, OperationKind.PROVE_CLEANUP})

# The closed parameter set per kind: (required, optional). A parameter not
# listed here does not exist for that kind, which is what makes "no arbitrary
# arguments" a property of the type rather than of a validator's mood.
_PARAMETERS: dict[OperationKind, tuple[tuple[str, ...], tuple[str, ...]]] = {
    OperationKind.ENSURE_IMAGE: (("image_digest",), ()),
    OperationKind.CREATE_RUNNER: (("registration_ref", "runner_name", "pool_id"), ()),
    OperationKind.MARK_DRAIN: (("reason",), ()),
    OperationKind.DESTROY_RUNNER: ((), ()),
    OperationKind.CANCEL_OR_TIMEOUT: (("reason",), ()),
    OperationKind.OBSERVE_RUNNER: ((), ()),
    OperationKind.PROVE_CLEANUP: ((), ()),
    OperationKind.ROLLBACK_ADAPTER: (("image_digest",), ()),
}

_SUBJECTS: dict[OperationKind, frozenset[SubjectKind]] = {
    OperationKind.ENSURE_IMAGE: frozenset({SubjectKind.HOST}),
    OperationKind.CREATE_RUNNER: frozenset({SubjectKind.RUNNER}),
    OperationKind.MARK_DRAIN: frozenset({SubjectKind.RUNNER, SubjectKind.HOST}),
    OperationKind.DESTROY_RUNNER: frozenset({SubjectKind.RUNNER}),
    OperationKind.CANCEL_OR_TIMEOUT: frozenset({SubjectKind.RUNNER}),
    OperationKind.OBSERVE_RUNNER: frozenset({SubjectKind.RUNNER}),
    OperationKind.PROVE_CLEANUP: frozenset({SubjectKind.RUNNER}),
    OperationKind.ROLLBACK_ADAPTER: frozenset({SubjectKind.HOST}),
}

# Adapter vocabulary -> contract vocabulary. The v1 receipt has no
# `ensure_image`; it has `apply`. Declared once, here, and tested against the
# contract's enum so the two cannot drift apart silently.
_CONTRACT_OPERATION: dict[OperationKind, str] = {
    OperationKind.ENSURE_IMAGE: "apply",
    OperationKind.CREATE_RUNNER: "assign",
    OperationKind.MARK_DRAIN: "drain",
    OperationKind.DESTROY_RUNNER: "release",
    OperationKind.CANCEL_OR_TIMEOUT: "release",
    OperationKind.ROLLBACK_ADAPTER: "apply",
}


def _value(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise OperationRefused(f"operation.parameters[{name}]: must be a string")
    if len(value) > _MAX_VALUE:
        raise OperationRefused(
            f"operation.parameters[{name}]: exceeds {_MAX_VALUE} characters"
        )
    if _SECRET_SHAPED.search(value):
        # Never echoed: the message says what happened, not what was sent.
        raise OperationRefused(
            f"operation.parameters[{name}]: looks like a credential value; "
            "an operation carries references, never secrets"
        )
    return value


def _checked_value(kind: OperationKind, name: str, value: str) -> str:
    if name == "image_digest" and not _DIGEST.match(value):
        raise OperationRefused(
            "operation.parameters[image_digest]: must be an immutable "
            "sha256:<64 hex> digest"
        )
    if name == "registration_ref" and not _REFERENCE.match(value):
        raise OperationRefused(
            "operation.parameters[registration_ref]: must be an opaque "
            "'ref:<name>' reference, never the registration material itself"
        )
    if name == "pool_id":
        try:
            _identifier(value, "operation.parameters[pool_id]")
        except ValueError as exc:
            raise OperationRefused(str(exc)) from None
    if name == "runner_name":
        try:
            _identifier(value, "operation.parameters[runner_name]")
        except ValueError as exc:
            raise OperationRefused(str(exc)) from None
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class Subject:
    """What an operation acts on, in the receipt contract's vocabulary."""

    kind: SubjectKind
    subject_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, SubjectKind):
            options = ", ".join(kind.value for kind in SubjectKind)
            raise OperationRefused(f"subject.kind: must be one of {options}")
        try:
            _identifier(self.subject_id, "subject.subject_id")
        except ValueError as exc:
            raise OperationRefused(str(exc)) from None


@dataclass(frozen=True, slots=True, kw_only=True)
class Operation:
    """One typed instruction. There is no field in which a command could fit."""

    operation_key: str
    host_id: str
    kind: OperationKind
    subject: Subject
    issued_at: str
    parameters: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        try:
            _request_id(self.operation_key, "operation.operation_key")
        except ValueError as exc:
            raise OperationRefused(str(exc)) from None
        try:
            _identifier(self.host_id, "operation.host_id")
        except ValueError as exc:
            raise OperationRefused(str(exc)) from None
        if not isinstance(self.kind, OperationKind):
            options = ", ".join(kind.value for kind in OperationKind)
            raise OperationRefused(f"operation.kind: must be one of {options}")
        if not isinstance(self.subject, Subject):
            raise OperationRefused("operation.subject: must be a Subject")
        if self.subject.kind not in _SUBJECTS[self.kind]:
            allowed = ", ".join(sorted(kind.value for kind in _SUBJECTS[self.kind]))
            raise OperationRefused(
                f"operation.subject.kind: {self.kind.value} acts on {allowed}, "
                f"not {self.subject.kind.value}"
            )
        try:
            _timestamp(self.issued_at, "operation.issued_at")
        except ValueError as exc:
            raise OperationRefused(str(exc)) from None
        required, optional = _PARAMETERS[self.kind]
        if not isinstance(self.parameters, tuple):
            raise OperationRefused("operation.parameters: must be a tuple of pairs")
        seen: dict[str, str] = {}
        for index, pair in enumerate(self.parameters):
            if (
                not isinstance(pair, tuple) or len(pair) != 2
                or not isinstance(pair[0], str) or not isinstance(pair[1], str)
            ):
                raise OperationRefused(
                    f"operation.parameters[{index}]: must be a (name, value) pair of strings"
                )
            name, value = pair
            if name in _SHELL_SHAPED:
                # The whole point of a typed operation: "run this" is not a
                # thing an operation can say.
                raise OperationRefused(
                    f"operation.parameters[{index}].{name}: an operation has no "
                    "command, script, or environment; host agents expose no "
                    "remote shell"
                )
            if name not in required and name not in optional:
                raise OperationRefused(
                    f"operation.parameters[{index}].{name}: is not a parameter of "
                    f"{self.kind.value}"
                )
            if name in seen:
                raise OperationRefused(
                    f"operation.parameters[{index}].{name}: is given twice"
                )
            seen[name] = _checked_value(self.kind, name, _value(name, value))
        missing = [name for name in required if name not in seen]
        if missing:
            raise OperationRefused(
                f"operation.parameters: {self.kind.value} requires "
                f"{', '.join(missing)}"
            )
        # Stored sorted so two equal operations are equal values.
        object.__setattr__(self, "parameters", tuple(sorted(seen.items())))

    def parameter(self, name: str) -> str | None:
        for key, value in self.parameters:
            if key == name:
                return value
        return None

    @property
    def read_only(self) -> bool:
        return self.kind in READ_ONLY


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentCapabilities:
    """What a host agent declares it has installed. Nothing here is implied."""

    adapters: frozenset[Runtime] = frozenset()
    operations: frozenset[OperationKind] = frozenset()
    allow_cancel_or_timeout: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.adapters, frozenset):
            raise OperationRefused("capabilities.adapters: must be a frozenset")
        for adapter in self.adapters:
            if not isinstance(adapter, Runtime):
                raise OperationRefused(
                    f"capabilities.adapters: {adapter!r} is not a Runtime"
                )
        if not isinstance(self.operations, frozenset):
            raise OperationRefused("capabilities.operations: must be a frozenset")
        for operation in self.operations:
            if not isinstance(operation, OperationKind):
                raise OperationRefused(
                    f"capabilities.operations: {operation!r} is not an operation kind"
                )
        if not isinstance(self.allow_cancel_or_timeout, bool):
            raise OperationRefused("capabilities.allow_cancel_or_timeout: must be bool")

    def permits(self, kind: OperationKind) -> bool:
        return kind in self.operations


def permit(operation: Operation, capabilities: AgentCapabilities) -> None:
    """Refuse unless this agent declared that it may do this. Deny by default."""
    if not isinstance(operation, Operation):
        raise OperationRefused("permit: must be an Operation")
    if not isinstance(capabilities, AgentCapabilities):
        raise OperationRefused("permit: must be AgentCapabilities")
    if not capabilities.adapters:
        raise OperationRefused(
            "permit: the agent has no runtime adapter installed; it may not be "
            "given work"
        )
    if not capabilities.permits(operation.kind):
        raise OperationRefused(
            f"permit: {operation.kind.value} is not in this agent's allowlist"
        )
    if (
        operation.kind is OperationKind.CANCEL_OR_TIMEOUT
        and not capabilities.allow_cancel_or_timeout
    ):
        raise OperationRefused(
            "permit: cancel_or_timeout is refused without the explicit policy "
            "that authorizes it"
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Evidence:
    """Where proof of a mutation lives, and the digest of what is there."""

    digest: str
    location: str

    def __post_init__(self) -> None:
        if not isinstance(self.digest, str) or not _DIGEST.match(self.digest):
            raise OperationRefused("evidence.digest: must be sha256:<64 hex>")
        if not isinstance(self.location, str) or not self.location:
            raise OperationRefused("evidence.location: must be a non-empty string")
        if len(self.location) > _MAX_VALUE:
            raise OperationRefused(
                f"evidence.location: exceeds {_MAX_VALUE} characters"
            )

    def document(self) -> dict:
        return {"digest": self.digest, "location": self.location}


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentReceipt:
    """An agent's claim about one operation. Evidence, not authority."""

    operation_key: str
    host_id: str
    outcome: ReceiptOutcome
    finished_at: str
    evidence: Evidence | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        try:
            _request_id(self.operation_key, "receipt.operation_key")
            _identifier(self.host_id, "receipt.host_id")
        except ValueError as exc:
            raise OperationRefused(str(exc)) from None
        if not isinstance(self.outcome, ReceiptOutcome):
            options = ", ".join(outcome.value for outcome in ReceiptOutcome)
            raise OperationRefused(f"receipt.outcome: must be one of {options}")
        try:
            _timestamp(self.finished_at, "receipt.finished_at")
        except ValueError as exc:
            raise OperationRefused(str(exc)) from None
        if self.evidence is not None and not isinstance(self.evidence, Evidence):
            raise OperationRefused("receipt.evidence: must be an Evidence")
        if self.outcome is ReceiptOutcome.COMPLETED and self.evidence is None:
            raise OperationRefused(
                "receipt.evidence: a completion without evidence is not a receipt"
            )
        if self.detail is not None:
            if not isinstance(self.detail, str) or not self.detail:
                raise OperationRefused("receipt.detail: must be a non-empty string")
            if len(self.detail) > _MAX_VALUE:
                raise OperationRefused(
                    f"receipt.detail: exceeds {_MAX_VALUE} characters"
                )
            if _SECRET_SHAPED.search(self.detail):
                raise OperationRefused(
                    "receipt.detail: looks like a credential value; a receipt "
                    "carries references, never secrets"
                )


class OperationLedger:
    """Issued operations and the one receipt each may have.

    A key is a durable promise: issuing it again with the same operation is a
    retry and returns what was issued; issuing it again with *different* work is
    refused, because widening what a key covers is how a retry becomes a second
    mutation.
    """

    def __init__(self) -> None:
        self._issued: dict[str, Operation] = {}
        self._receipts: dict[str, AgentReceipt] = {}

    def issue(self, operation: Operation, capabilities: AgentCapabilities) -> Operation:
        if not isinstance(operation, Operation):
            raise OperationRefused("ledger.issue: must be an Operation")
        permit(operation, capabilities)
        existing = self._issued.get(operation.operation_key)
        if existing is not None:
            if existing != operation:
                raise OperationRefused(
                    "ledger.issue: this operation key was already issued for "
                    "different work; a key cannot be widened"
                )
            return existing
        self._issued[operation.operation_key] = operation
        return operation

    def issued(self, operation_key: str) -> Operation:
        found = self._issued.get(operation_key)
        if found is None:
            raise OperationRefused(
                "ledger: no operation was issued under this key"
            )
        return found

    def record(self, receipt: AgentReceipt) -> AgentReceipt:
        """Accept one receipt per operation, and only for work that was issued."""
        if not isinstance(receipt, AgentReceipt):
            raise OperationRefused("ledger.record: must be an AgentReceipt")
        operation = self.issued(receipt.operation_key)
        if operation.read_only:
            raise OperationRefused(
                f"ledger.record: {operation.kind.value} changes nothing, so there "
                "is nothing to attest"
            )
        if receipt.host_id != operation.host_id:
            raise OperationRefused(
                "ledger.record: the receipt is from a different host than the "
                "operation was issued to"
            )
        # A completion without evidence cannot reach here: `AgentReceipt`
        # refuses it at construction, and that is where the rule lives. A second
        # copy here would be a check nothing can reach — found by mutation M18,
        # which survived precisely because the guard was dead.
        existing = self._receipts.get(receipt.operation_key)
        if existing is not None:
            if existing != receipt:
                raise OperationRefused(
                    "ledger.record: this operation already has a receipt, and this "
                    "one says something different; the first answer is the answer"
                )
            return existing
        self._receipts[receipt.operation_key] = receipt
        return receipt

    def receipt(self, operation_key: str) -> AgentReceipt:
        found = self._receipts.get(operation_key)
        if found is None:
            raise OperationRefused("ledger: no receipt was recorded for this key")
        return found

    def authoritative_receipt(
        self, operation_key: str, *, receipt_id: str, issued_at: str,
        actor_id: str = "fleet-manager",
    ) -> dict:
        """The contract-v1 document the evidence plane consumes.

        Built by the manager from the agent's claim. The claim is not forwarded:
        it is mapped, and the mapping is declared above.
        """
        operation = self.issued(operation_key)
        receipt = self.receipt(operation_key)
        contract_operation = _CONTRACT_OPERATION.get(operation.kind)
        if contract_operation is None:
            # A read-only kind, or a kind added without a mapping. Either way
            # there is no contract vocabulary to build from, and the refusal
            # names that rather than failing as a missing dict key.
            raise OperationRefused(
                f"ledger: {operation.kind.value} has no declared contract "
                "operation; a read-only operation produces no contract receipt"
            )
        return build_receipt(
            receipt_id=receipt_id,
            issued_at=issued_at,
            subject={
                "kind": operation.subject.kind.value,
                "id": operation.subject.subject_id,
            },
            operation=contract_operation,
            outcome=receipt.outcome.value,
            actor={"kind": "host_agent", "id": actor_id},
            evidence=receipt.evidence.document() if receipt.evidence else None,
            detail=receipt.detail,
        )


# --- runner-enroll.sh: the declared migration ------------------------------
#
# The existing enrollment script predates Fleet Manager and talks to the monitor
# hub. Its inputs are not silently dropped: each is mapped here to the thing
# that now carries the duty, and a test reads the script and fails if it grows
# an option this table does not account for.
RUNNER_ENROLL_MIGRATION: dict[str, tuple[str, str]] = {
    "--host-alias": (
        "host_id",
        "the enrollment token's host binding is the authority; an alias is a "
        "label, not an identity",
    ),
    "--repo": (
        "pool.allowed_repositories",
        "declared in desired state for the pool, not passed per enrollment",
    ),
    "--labels": (
        "pool.required_labels",
        "declared in desired state for the pool",
    ),
    "--runner-name": (
        "create_runner.runner_name",
        "a parameter of the operation that creates the runner, not a host "
        "identity",
    ),
    "--interval": (
        "agent poll",
        "the outbound agent's poll replaces the heartbeat systemd timer",
    ),
    "--revoke": (
        "AgentChannel.revoke",
        "revocation is a manager-side call; re-enrollment needs a new token",
    ),
}
