# spec: fleet-001-02, fleet-001-03
"""Desired state as the store will keep it (Sprint 2 box 2.1).

Documents are closed in both directions. Missing fields are named; unknown
fields are refused. The pull toward leniency is real — it makes a future field
cheap — but a store that silently drops what it does not understand will one
day drop `secret_profile` and keep serving, which is indistinguishable from
having honoured it.

Secrets are referenced, never carried (fleet-001-03). Any key shaped like a
secret *value* is refused anywhere in the document; the declared reference
fields (`secret_profile`) must hold an identifier, not a blob. Refusals name the
path and never repeat the value, so the diagnostic cannot become the store.
"""
from __future__ import annotations

import re
from typing import Any, Callable, TypeVar

from .model import (
    Assignment,
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

DOCUMENT_SCHEMA = "fleet-manager-desired-state/1"

T = TypeVar("T")

# A key shaped like a secret *value*. `secret_profile` is the one declared
# reference field and is exempt; everything else matching this is refused
# outright rather than inspected, because inspecting it is how it gets logged.
_SECRET_KEY = re.compile(
    r"(?i)(^|[_-])(token|password|passwd|secret|api[_-]?key|private[_-]?key|credential)s?($|[_-])"
)
_REFERENCE_KEYS = frozenset({"secret_profile"})


def _object(value: object, where: str) -> dict:
    if not isinstance(value, dict):
        raise ModelError(f"{where}: must be an object")
    return value


def _list(value: object, where: str) -> list:
    if isinstance(value, str) or not isinstance(value, list):
        raise ModelError(f"{where}: must be a list")
    return value


def _pairs(value: object, where: str) -> tuple[tuple[str, str], ...]:
    obj = _object(value, where)
    return tuple(sorted((str(key), str(item)) for key, item in obj.items()))


def _enum(kind, value: object, where: str):
    if isinstance(value, kind):
        return value
    try:
        return kind(value)
    except (ValueError, TypeError):
        options = ", ".join(member.value for member in kind)
        raise ModelError(f"{where}: must be one of {options}") from None


def _shape(doc: dict, where: str, required: tuple[str, ...], optional: tuple[str, ...] = ()) -> None:
    missing = [key for key in required if key not in doc]
    if missing:
        raise ModelError(f"{where}: missing required field(s): {', '.join(sorted(missing))}")
    unknown = sorted(set(doc) - set(required) - set(optional))
    if unknown:
        raise ModelError(f"{where}: unknown field(s): {', '.join(unknown)}")


def _build(where: str, make: Callable[[], T]) -> T:
    try:
        return make()
    except ModelError as exc:
        raise ModelError(f"{where}: {exc}") from None


def _reject_secret_values(node: Any, path: str) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if _SECRET_KEY.search(str(key)) and str(key) not in _REFERENCE_KEYS:
                raise ModelError(
                    f"{path}.{key}: secret-shaped fields are not representable in "
                    "desired state — reference a secret profile instead"
                )
            _reject_secret_values(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _reject_secret_values(item, f"{path}[{index}]")


# --- per-value documents ---------------------------------------------------

_REPOSITORY_REQUIRED = ("name", "trust_class")
_REPOSITORY_OPTIONAL = ("runner_group",)


def repository_to_document(repository: Repository) -> dict:
    return {
        "name": repository.name,
        "trust_class": repository.trust_class.value,
        "runner_group": repository.runner_group,
    }


def repository_from_document(doc: object, where: str = "repository") -> Repository:
    doc = _object(doc, where)
    _reject_secret_values(doc, where)
    _shape(doc, where, _REPOSITORY_REQUIRED, _REPOSITORY_OPTIONAL)
    return _build(
        where,
        lambda: Repository(
            name=doc["name"],
            trust_class=_enum(TrustClass, doc["trust_class"], f"{where}.trust_class"),
            runner_group=doc.get("runner_group"),
        ),
    )


_POOL_REQUIRED = (
    "pool_id",
    "revision",
    "trust_class",
    "required_labels",
    "runtime",
    "image_digest",
    "architectures",
    "warm_min",
    "warm_max",
    "scale_ceiling",
    "idle_timeout_seconds",
    "job_timeout_seconds",
    "cleanup_timeout_seconds",
    "network_profile",
    "filesystem_profile",
    "secret_profile",
    "update_channel",
    "rollback_image_digest",
    "maintenance_window",
    "disruption_budget",
    "owner",
    "escalation",
)
_POOL_OPTIONAL = ("allowed_repositories", "runner_group", "ephemeral")


def pool_to_document(pool: Pool) -> dict:
    return {
        "pool_id": pool.pool_id,
        "revision": pool.revision,
        "trust_class": pool.trust_class.value,
        "allowed_repositories": list(pool.allowed_repositories),
        "runner_group": pool.runner_group,
        "required_labels": dict(pool.required_labels),
        "runtime": pool.runtime.value,
        "image_digest": pool.image_digest,
        "architectures": list(pool.architectures),
        "ephemeral": pool.ephemeral,
        "warm_min": pool.warm_min,
        "warm_max": pool.warm_max,
        "scale_ceiling": pool.scale_ceiling,
        "idle_timeout_seconds": pool.idle_timeout_seconds,
        "job_timeout_seconds": pool.job_timeout_seconds,
        "cleanup_timeout_seconds": pool.cleanup_timeout_seconds,
        "network_profile": pool.network_profile,
        "filesystem_profile": pool.filesystem_profile,
        "secret_profile": pool.secret_profile,
        "update_channel": pool.update_channel,
        "rollback_image_digest": pool.rollback_image_digest,
        "maintenance_window": pool.maintenance_window,
        "disruption_budget": {"max_parallel": pool.disruption_budget.max_parallel},
        "owner": pool.owner,
        "escalation": pool.escalation,
    }


def pool_from_document(doc: object, where: str = "pool") -> Pool:
    doc = _object(doc, where)
    _reject_secret_values(doc, where)
    _shape(doc, where, _POOL_REQUIRED, _POOL_OPTIONAL)
    budget = _object(doc["disruption_budget"], f"{where}.disruption_budget")
    _shape(budget, f"{where}.disruption_budget", ("max_parallel",))
    return _build(
        where,
        lambda: Pool(
            pool_id=doc["pool_id"],
            revision=doc["revision"],
            trust_class=_enum(TrustClass, doc["trust_class"], f"{where}.trust_class"),
            allowed_repositories=tuple(
                _list(doc.get("allowed_repositories", []), f"{where}.allowed_repositories")
            ),
            runner_group=doc.get("runner_group"),
            required_labels=_pairs(doc["required_labels"], f"{where}.required_labels"),
            runtime=_enum(Runtime, doc["runtime"], f"{where}.runtime"),
            image_digest=doc["image_digest"],
            architectures=tuple(_list(doc["architectures"], f"{where}.architectures")),
            ephemeral=doc.get("ephemeral", True),
            warm_min=doc["warm_min"],
            warm_max=doc["warm_max"],
            scale_ceiling=doc["scale_ceiling"],
            idle_timeout_seconds=doc["idle_timeout_seconds"],
            job_timeout_seconds=doc["job_timeout_seconds"],
            cleanup_timeout_seconds=doc["cleanup_timeout_seconds"],
            network_profile=doc["network_profile"],
            filesystem_profile=doc["filesystem_profile"],
            secret_profile=doc["secret_profile"],
            update_channel=doc["update_channel"],
            rollback_image_digest=doc["rollback_image_digest"],
            maintenance_window=doc["maintenance_window"],
            disruption_budget=DisruptionBudget(max_parallel=budget["max_parallel"]),
            owner=doc["owner"],
            escalation=doc["escalation"],
        ),
    )


_HOST_REQUIRED = (
    "host_id",
    "architectures",
    "runtimes",
    "labels",
    "allowed_pools",
    "slots",
)


def host_to_document(host: Host) -> dict:
    return {
        "host_id": host.host_id,
        "architectures": list(host.architectures),
        "runtimes": [runtime.value for runtime in host.runtimes],
        "labels": dict(host.labels),
        "allowed_pools": list(host.allowed_pools),
        "slots": host.slots,
        "state": host.state.value,
    }


def host_from_document(doc: object, where: str = "host") -> Host:
    doc = _object(doc, where)
    _reject_secret_values(doc, where)
    _shape(doc, where, _HOST_REQUIRED, ("state",))
    return _build(
        where,
        lambda: Host(
            host_id=doc["host_id"],
            architectures=tuple(_list(doc["architectures"], f"{where}.architectures")),
            runtimes=tuple(
                _enum(Runtime, item, f"{where}.runtimes[{index}]")
                for index, item in enumerate(_list(doc["runtimes"], f"{where}.runtimes"))
            ),
            labels=_pairs(doc["labels"], f"{where}.labels"),
            allowed_pools=tuple(_list(doc["allowed_pools"], f"{where}.allowed_pools")),
            slots=doc["slots"],
            state=_enum(HostState, doc.get("state", HostState.ACTIVE.value), f"{where}.state"),
        ),
    )


_ASSIGNMENT_REQUIRED = ("assignment_id", "request_id", "pool_id", "host_id", "issued_at")


def assignment_to_document(assignment: Assignment) -> dict:
    return {
        "assignment_id": assignment.assignment_id,
        "request_id": assignment.request_id,
        "pool_id": assignment.pool_id,
        "host_id": assignment.host_id,
        "issued_at": assignment.issued_at,
        "released_at": assignment.released_at,
    }


def assignment_from_document(doc: object, where: str = "assignment") -> Assignment:
    doc = _object(doc, where)
    _reject_secret_values(doc, where)
    _shape(doc, where, _ASSIGNMENT_REQUIRED, ("released_at",))
    return _build(
        where,
        lambda: Assignment(
            assignment_id=doc["assignment_id"],
            request_id=doc["request_id"],
            pool_id=doc["pool_id"],
            host_id=doc["host_id"],
            issued_at=doc["issued_at"],
            released_at=doc.get("released_at"),
        ),
    )


_DRAIN_REQUIRED = ("host_id", "reason", "requested_at")


def drain_to_document(drain: Drain) -> dict:
    return {
        "host_id": drain.host_id,
        "reason": drain.reason,
        "requested_at": drain.requested_at,
        "state": drain.state.value,
        "completed_at": drain.completed_at,
        "ended_at": drain.ended_at,
    }


def drain_from_document(doc: object, where: str = "drain") -> Drain:
    doc = _object(doc, where)
    _reject_secret_values(doc, where)
    _shape(doc, where, _DRAIN_REQUIRED, ("state", "completed_at", "ended_at"))
    return _build(
        where,
        lambda: Drain(
            host_id=doc["host_id"],
            reason=doc["reason"],
            requested_at=doc["requested_at"],
            state=_enum(DrainState, doc.get("state", DrainState.DRAINING.value), f"{where}.state"),
            completed_at=doc.get("completed_at"),
            ended_at=doc.get("ended_at"),
        ),
    )


_ROLLOUT_REQUIRED = (
    "rollout_id",
    "pool_id",
    "from_image_digest",
    "to_image_digest",
    "started_at",
)


def rollout_to_document(rollout: Rollout) -> dict:
    return {
        "rollout_id": rollout.rollout_id,
        "pool_id": rollout.pool_id,
        "from_image_digest": rollout.from_image_digest,
        "to_image_digest": rollout.to_image_digest,
        "started_at": rollout.started_at,
        "state": rollout.state.value,
    }


def rollout_from_document(doc: object, where: str = "rollout") -> Rollout:
    doc = _object(doc, where)
    _reject_secret_values(doc, where)
    _shape(doc, where, _ROLLOUT_REQUIRED, ("state",))
    return _build(
        where,
        lambda: Rollout(
            rollout_id=doc["rollout_id"],
            pool_id=doc["pool_id"],
            from_image_digest=doc["from_image_digest"],
            to_image_digest=doc["to_image_digest"],
            started_at=doc["started_at"],
            state=_enum(RolloutState, doc.get("state", RolloutState.IN_PROGRESS.value), f"{where}.state"),
        ),
    )


# --- the aggregate document ------------------------------------------------

_TOP_REQUIRED = ("schema", "revision")
_TOP_OPTIONAL = ("repositories", "pools", "hosts", "assignments", "drains", "rollouts")


def to_document(state: DesiredState) -> dict:
    return {
        "schema": DOCUMENT_SCHEMA,
        "revision": state.revision,
        "repositories": [repository_to_document(item) for item in state.repositories],
        "pools": [pool_to_document(item) for item in state.pools],
        "hosts": [host_to_document(item) for item in state.hosts],
        "assignments": [assignment_to_document(item) for item in state.assignments],
        "drains": [drain_to_document(item) for item in state.drains],
        "rollouts": [rollout_to_document(item) for item in state.rollouts],
    }


def from_document(doc: object) -> DesiredState:
    where = "desired_state"
    doc = _object(doc, where)
    _reject_secret_values(doc, where)
    _shape(doc, where, _TOP_REQUIRED, _TOP_OPTIONAL)
    if doc["schema"] != DOCUMENT_SCHEMA:
        raise ModelError(f"{where}.schema: must be {DOCUMENT_SCHEMA!r}")

    def items(key: str, parse):
        raw = _list(doc.get(key, []), f"{where}.{key}")
        return tuple(
            parse(item, f"{where}.{key}[{index}]")
            for index, item in enumerate(raw)
        )

    return _build(
        where,
        lambda: DesiredState(
            revision=doc["revision"],
            repositories=items("repositories", repository_from_document),
            pools=items("pools", pool_from_document),
            hosts=items("hosts", host_from_document),
            assignments=items("assignments", assignment_from_document),
            drains=items("drains", drain_from_document),
            rollouts=items("rollouts", rollout_from_document),
        ),
    )
