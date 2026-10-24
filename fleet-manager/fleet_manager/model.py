# spec: fleet-001-01, fleet-001-02, fleet-001-04, fleet-001-05
"""Fleet Manager desired-state model (FLEET-001, Sprint 2 box 2.1).

Desired state is the manager's, and only the manager's. Host agents report
observations (`observation.py`), which this module neither imports nor accepts;
turning a report into desired state takes an explicit operation here, and that
operation produces a new revision.

Every value in this module is frozen. A transition never edits the value it was
given — it returns a new `DesiredState` at `revision + 1`, so an applied
revision names a complete world rather than a set of edits (FLEET-002: "apply
against the same desired-state revision" needs a value to compare against).

Nothing here opens a socket, reads a file, or shells out. `Runtime` names the
adapters Sprint 4 will build; it does not call them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable, Sequence

# Lowercase, dot-separated identifiers: pool ids, host ids, profiles, owners.
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
# The same shape the v1 capacity contract accepts, so a request id can be
# carried here without translation.
_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_FREE_TEXT = re.compile(r"^[A-Za-z0-9 .,:/_+-]{1,96}$")

UPDATE_CHANNELS = frozenset({"stable", "canary", "pinned"})


class ModelError(ValueError):
    """A desired-state value that cannot exist.

    Messages name the field and the rule. They never repeat the offending
    value: a diagnostic that echoes a rejected secret is a secret store
    (fleet-001-03).
    """


class TrustClass(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    ISOLATED = "isolated"


class Runtime(str, Enum):
    DOCKER = "docker"
    PODMAN = "podman"


class HostState(str, Enum):
    ACTIVE = "active"
    DRAINING = "draining"
    DRAINED = "drained"
    MAINTENANCE = "maintenance"


class AssignmentState(str, Enum):
    ASSIGNED = "assigned"
    RELEASED = "released"


class DrainState(str, Enum):
    DRAINING = "draining"
    DRAINED = "drained"
    ENDED = "ended"


class RolloutState(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"


# --- scalar validation -----------------------------------------------------


def _identifier(value: object, where: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.match(value):
        raise ModelError(
            f"{where}: must be a lowercase identifier (a-z 0-9 . _ -, 1-64 chars)"
        )
    return value


def _request_id(value: object, where: str) -> str:
    if not isinstance(value, str) or not _REQUEST_ID.match(value):
        raise ModelError(f"{where}: must match [A-Za-z0-9][A-Za-z0-9._:-]{{0,127}}")
    return value


def _repository(value: object, where: str) -> str:
    if not isinstance(value, str) or not _REPOSITORY.match(value):
        raise ModelError(f"{where}: must be owner/name")
    return value


def _digest(value: object, where: str) -> str:
    if not isinstance(value, str) or not _DIGEST.match(value):
        raise ModelError(
            f"{where}: must be a pinned digest, sha256:<64 lowercase hex> "
            "(tags and 'latest' cannot be pinned)"
        )
    return value


def _text(value: object, where: str) -> str:
    if not isinstance(value, str) or not _FREE_TEXT.match(value):
        raise ModelError(f"{where}: must be short free text (letters, digits, . , : / _ + -)")
    return value


def _count(value: object, where: str, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ModelError(f"{where}: must be an integer >= {minimum}")
    return value


def _timestamp(value: object, where: str) -> str:
    if not isinstance(value, str):
        raise ModelError(f"{where}: must be an ISO-8601 timestamp with a timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ModelError(
            f"{where}: must be an ISO-8601 timestamp with a timezone"
        ) from None
    if parsed.tzinfo is None:
        raise ModelError(f"{where}: must carry a timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def _choice(value: object, where: str, allowed: Iterable[str], enum_type=None):
    if enum_type is not None:
        if not isinstance(value, enum_type):
            options = ", ".join(member.value for member in enum_type)
            raise ModelError(f"{where}: must be one of {options}")
        return value
    if value not in allowed:
        raise ModelError(f"{where}: must be one of {', '.join(sorted(allowed))}")
    return value


def _labels(value: object, where: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, dict) or not value:
        raise ModelError(f"{where}: must be a non-empty object of label name -> value")
    pairs = []
    for key, item in value.items():
        _identifier(key, f"{where}.{key}")
        if not isinstance(item, str) or not item or len(item) > 96:
            raise ModelError(f"{where}.{key}: label values must be 1-96 characters")
        pairs.append((key, item))
    return tuple(sorted(pairs))


def _identifiers(value: object, where: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence) or not value:
        raise ModelError(f"{where}: must be a non-empty list")
    return tuple(_identifier(item, f"{where}[{index}]") for index, item in enumerate(value))


def _digests_differ(one: str, other: str, where: str) -> None:
    if one == other:
        raise ModelError(f"{where}: rollback image must differ from the current image")


# --- values ----------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class DisruptionBudget:
    """How much of a pool may be disturbed at once (FLEET-003 input)."""

    max_parallel: int = 1

    def __post_init__(self) -> None:
        _count(self.max_parallel, "disruption_budget.max_parallel", minimum=1)


@dataclass(frozen=True, slots=True, kw_only=True)
class Repository:
    name: str
    trust_class: TrustClass
    runner_group: str | None = None

    def __post_init__(self) -> None:
        _repository(self.name, "repository.name")
        _choice(self.trust_class, "repository.trust_class", (), TrustClass)
        if self.runner_group is not None:
            _identifier(self.runner_group, "repository.runner_group")


@dataclass(frozen=True, slots=True, kw_only=True)
class Pool:
    """A runner pool's desired contract (program §4.3).

    `revision` is the pool's own revision — the contract changed — as distinct
    from `DesiredState.revision`, which covers the whole world. They are
    separate because a pool edit and an unrelated drain must not be forced to
    share a number.
    """

    pool_id: str
    revision: int
    trust_class: TrustClass
    required_labels: tuple[tuple[str, str], ...]
    runtime: Runtime
    image_digest: str
    architectures: tuple[str, ...]
    warm_min: int
    warm_max: int
    scale_ceiling: int
    idle_timeout_seconds: int
    job_timeout_seconds: int
    cleanup_timeout_seconds: int
    network_profile: str
    filesystem_profile: str
    secret_profile: str
    update_channel: str
    rollback_image_digest: str
    maintenance_window: str
    disruption_budget: DisruptionBudget
    owner: str
    escalation: str
    allowed_repositories: tuple[str, ...] = ()
    runner_group: str | None = None
    ephemeral: bool = True

    def __post_init__(self) -> None:
        _identifier(self.pool_id, "pool.pool_id")
        _count(self.revision, "pool.revision", minimum=1)
        _choice(self.trust_class, "pool.trust_class", (), TrustClass)
        _choice(self.runtime, "pool.runtime", (), Runtime)
        _digest(self.image_digest, "pool.image_digest")
        _digest(self.rollback_image_digest, "pool.rollback_image_digest")
        _digests_differ(self.rollback_image_digest, self.image_digest, "pool")
        if not isinstance(self.required_labels, tuple) or not self.required_labels:
            raise ModelError("pool.required_labels: must be a non-empty label set")
        for key, item in self.required_labels:
            _identifier(key, f"pool.required_labels.{key}")
            if not isinstance(item, str) or not item or len(item) > 96:
                raise ModelError(f"pool.required_labels.{key}: label values must be 1-96 characters")
        if not isinstance(self.architectures, tuple) or not self.architectures:
            raise ModelError("pool.architectures: must be a non-empty tuple")
        for index, arch in enumerate(self.architectures):
            _identifier(arch, f"pool.architectures[{index}]")
        if self.ephemeral is not True:
            raise ModelError(
                "pool.ephemeral: must be true — the v1 capacity contract declares "
                "demand.ephemeral as const true, so a persistent pool would be a "
                "fleet the contract cannot request"
            )
        _count(self.warm_min, "pool.warm_min")
        _count(self.warm_max, "pool.warm_max", minimum=1)
        _count(self.scale_ceiling, "pool.scale_ceiling", minimum=1)
        if not self.warm_min <= self.warm_max <= self.scale_ceiling:
            raise ModelError(
                "pool warm bounds: warm_min <= warm_max <= scale_ceiling must hold"
            )
        _count(self.idle_timeout_seconds, "pool.idle_timeout_seconds", minimum=1)
        _count(self.job_timeout_seconds, "pool.job_timeout_seconds", minimum=1)
        _count(self.cleanup_timeout_seconds, "pool.cleanup_timeout_seconds", minimum=1)
        _identifier(self.network_profile, "pool.network_profile")
        _identifier(self.filesystem_profile, "pool.filesystem_profile")
        _identifier(self.secret_profile, "pool.secret_profile")
        _choice(self.update_channel, "pool.update_channel", UPDATE_CHANNELS)
        _text(self.maintenance_window, "pool.maintenance_window")
        if not isinstance(self.disruption_budget, DisruptionBudget):
            raise ModelError("pool.disruption_budget: must be a DisruptionBudget")
        _text(self.owner, "pool.owner")
        _text(self.escalation, "pool.escalation")
        # Exactly one of "these repositories" or "this runner group" (program
        # §4.3: "allowed repositories or runner group") — both would leave the
        # answer to "who may run here" undefined.
        repositories = tuple(
            _repository(name, f"pool.allowed_repositories[{index}]")
            for index, name in enumerate(self.allowed_repositories)
        )
        if bool(repositories) == (self.runner_group is not None):
            raise ModelError(
                "pool scope: declare exactly one of allowed_repositories or runner_group"
            )
        if self.runner_group is not None:
            _identifier(self.runner_group, "pool.runner_group")

    def with_image(self, image_digest: str, rollback_image_digest: str) -> Pool:
        """A new pool revision carrying a new image and its rollback."""
        return replace(
            self,
            revision=self.revision + 1,
            image_digest=image_digest,
            rollback_image_digest=rollback_image_digest,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Host:
    host_id: str
    architectures: tuple[str, ...]
    runtimes: tuple[Runtime, ...]
    labels: tuple[tuple[str, str], ...]
    allowed_pools: tuple[str, ...]
    slots: int
    state: HostState = HostState.ACTIVE

    def __post_init__(self) -> None:
        _identifier(self.host_id, "host.host_id")
        if not isinstance(self.architectures, tuple) or not self.architectures:
            raise ModelError("host.architectures: must be a non-empty tuple")
        for index, arch in enumerate(self.architectures):
            _identifier(arch, f"host.architectures[{index}]")
        if not isinstance(self.runtimes, tuple) or not self.runtimes:
            raise ModelError("host.runtimes: must be a non-empty tuple")
        for index, runtime in enumerate(self.runtimes):
            _choice(runtime, f"host.runtimes[{index}]", (), Runtime)
        if not isinstance(self.labels, tuple):
            raise ModelError("host.labels: must be a tuple of (name, value) pairs")
        for key, item in self.labels:
            _identifier(key, f"host.labels.{key}")
            if not isinstance(item, str) or not item:
                raise ModelError(f"host.labels.{key}: label values must be non-empty")
        _identifiers(self.allowed_pools, "host.allowed_pools")
        _count(self.slots, "host.slots", minimum=1)
        _choice(self.state, "host.state", (), HostState)

    def refusal_for(self, pool: Pool) -> str | None:
        """Why this host cannot run `pool`, or None when it can (fleet-001-04)."""
        if self.state is not HostState.ACTIVE:
            return f"host is {self.state.value}"
        if pool.runtime not in self.runtimes:
            return f"host does not offer runtime {pool.runtime.value}"
        if not set(pool.architectures) & set(self.architectures):
            return "host architectures do not intersect the pool's"
        if pool.pool_id not in self.allowed_pools:
            return "pool is not on the host's allow-list"
        return None


@dataclass(frozen=True, slots=True, kw_only=True)
class Assignment:
    assignment_id: str
    request_id: str
    pool_id: str
    host_id: str
    issued_at: str
    released_at: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.assignment_id, "assignment.assignment_id")
        _request_id(self.request_id, "assignment.request_id")
        _identifier(self.pool_id, "assignment.pool_id")
        _identifier(self.host_id, "assignment.host_id")
        _timestamp(self.issued_at, "assignment.issued_at")
        if self.released_at is not None:
            _timestamp(self.released_at, "assignment.released_at")
            if self.released_at < self.issued_at:
                raise ModelError("assignment.released_at: must not precede issued_at")

    @property
    def state(self) -> AssignmentState:
        return (
            AssignmentState.RELEASED
            if self.released_at is not None
            else AssignmentState.ASSIGNED
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Capacity:
    total: int
    in_use: int

    def __post_init__(self) -> None:
        _count(self.total, "capacity.total")
        _count(self.in_use, "capacity.in_use")
        if self.in_use > self.total:
            raise ModelError("capacity.in_use: cannot exceed capacity.total")

    @property
    def free(self) -> int:
        return self.total - self.in_use

    @property
    def saturated(self) -> bool:
        return self.free == 0


@dataclass(frozen=True, slots=True, kw_only=True)
class Drain:
    host_id: str
    reason: str
    requested_at: str
    state: DrainState = DrainState.DRAINING
    completed_at: str | None = None
    ended_at: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.host_id, "drain.host_id")
        _text(self.reason, "drain.reason")
        _timestamp(self.requested_at, "drain.requested_at")
        _choice(self.state, "drain.state", (), DrainState)


@dataclass(frozen=True, slots=True, kw_only=True)
class Rollout:
    rollout_id: str
    pool_id: str
    from_image_digest: str
    to_image_digest: str
    started_at: str
    state: RolloutState = RolloutState.IN_PROGRESS

    def __post_init__(self) -> None:
        _identifier(self.rollout_id, "rollout.rollout_id")
        _identifier(self.pool_id, "rollout.pool_id")
        _digest(self.from_image_digest, "rollout.from_image_digest")
        _digest(self.to_image_digest, "rollout.to_image_digest")
        if self.from_image_digest == self.to_image_digest:
            raise ModelError("rollout: from and to image digests must differ")
        _timestamp(self.started_at, "rollout.started_at")
        _choice(self.state, "rollout.state", (), RolloutState)


# --- the aggregate ---------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class DesiredState:
    """One complete world at one revision. Never edited, only replaced."""

    revision: int
    repositories: tuple[Repository, ...] = ()
    pools: tuple[Pool, ...] = ()
    hosts: tuple[Host, ...] = ()
    assignments: tuple[Assignment, ...] = ()
    drains: tuple[Drain, ...] = ()
    rollouts: tuple[Rollout, ...] = ()

    def __post_init__(self) -> None:
        _count(self.revision, "desired_state.revision", minimum=1)
        # Type checks first: an observation shares field names with a host, so
        # "it has a host_id" is not evidence that it belongs here (fleet-001-01).
        _typed(self.repositories, Repository, "desired_state.repositories")
        _typed(self.pools, Pool, "desired_state.pools")
        _typed(self.hosts, Host, "desired_state.hosts")
        _typed(self.assignments, Assignment, "desired_state.assignments")
        _typed(self.drains, Drain, "desired_state.drains")
        _typed(self.rollouts, Rollout, "desired_state.rollouts")
        _unique(self.repositories, "name", "desired_state.repositories")
        _unique(self.pools, "pool_id", "desired_state.pools")
        _unique(self.hosts, "host_id", "desired_state.hosts")
        _unique(self.assignments, "assignment_id", "desired_state.assignments")
        _unique(self.rollouts, "rollout_id", "desired_state.rollouts")
        pool_ids = {pool.pool_id for pool in self.pools}
        host_ids = {host.host_id for host in self.hosts}
        for assignment in self.assignments:
            if assignment.pool_id not in pool_ids:
                raise ModelError(
                    f"desired_state.assignments: references unknown pool "
                    f"{assignment.pool_id}"
                )
            if assignment.host_id not in host_ids:
                raise ModelError(
                    f"desired_state.assignments: references unknown host "
                    f"{assignment.host_id}"
                )
        for drain in self.drains:
            if drain.host_id not in host_ids:
                raise ModelError(
                    f"desired_state.drains: references unknown host {drain.host_id}"
                )
        for rollout in self.rollouts:
            if rollout.pool_id not in pool_ids:
                raise ModelError(
                    f"desired_state.rollouts: references unknown pool {rollout.pool_id}"
                )

    # lookups

    def pool(self, pool_id: str) -> Pool:
        for pool in self.pools:
            if pool.pool_id == pool_id:
                return pool
        raise ModelError(f"pool: no pool {pool_id} in revision {self.revision}")

    def host(self, host_id: str) -> Host:
        for host in self.hosts:
            if host.host_id == host_id:
                return host
        raise ModelError(f"host: no host {host_id} in revision {self.revision}")

    def assignment(self, assignment_id: str) -> Assignment:
        for assignment in self.assignments:
            if assignment.assignment_id == assignment_id:
                return assignment
        raise ModelError(
            f"assignment: no assignment {assignment_id} in revision {self.revision}"
        )

    def active_drain(self, host_id: str) -> Drain | None:
        for drain in reversed(self.drains):
            if drain.host_id == host_id and drain.state is not DrainState.ENDED:
                return drain
        return None

    def capacity(self, host_id: str) -> Capacity:
        host = self.host(host_id)
        in_use = sum(
            1
            for assignment in self.assignments
            if assignment.host_id == host_id
            and assignment.state is AssignmentState.ASSIGNED
        )
        return Capacity(total=host.slots, in_use=in_use)

    # transitions (each returns a new revision)

    def _bumped(self, **changes) -> DesiredState:
        return replace(self, revision=self.revision + 1, **changes)

    def _with_host(self, host_id: str, **changes) -> tuple[Host, ...]:
        return tuple(
            replace(host, **changes) if host.host_id == host_id else host
            for host in self.hosts
        )

    def _with_pool(self, pool_id: str, **changes) -> tuple[Pool, ...]:
        return tuple(
            replace(pool, **changes) if pool.pool_id == pool_id else pool
            for pool in self.pools
        )

    def with_assignment(
        self, *, assignment_id: str, request_id: str, pool_id: str, host_id: str, at: str
    ) -> DesiredState:
        pool = self.pool(pool_id)
        host = self.host(host_id)
        reason = host.refusal_for(pool)
        if reason is not None:
            raise ModelError(f"assignment refused: {reason}")
        capacity = self.capacity(host_id)
        if capacity.saturated:
            raise ModelError(
                f"assignment refused: host is at capacity "
                f"(total {capacity.total}, in_use {capacity.in_use}, free {capacity.free})"
            )
        assignment = Assignment(
            assignment_id=assignment_id,
            request_id=request_id,
            pool_id=pool_id,
            host_id=host_id,
            issued_at=at,
        )
        if any(item.assignment_id == assignment_id for item in self.assignments):
            raise ModelError(f"assignment refused: {assignment_id} already exists")
        return self._bumped(assignments=self.assignments + (assignment,))

    def with_release(self, *, assignment_id: str, at: str) -> DesiredState:
        assignment = self.assignment(assignment_id)
        if assignment.state is AssignmentState.RELEASED:
            raise ModelError(f"release refused: {assignment_id} is already released")
        _timestamp(at, "release.at")
        releases = tuple(
            replace(item, released_at=at) if item.assignment_id == assignment_id else item
            for item in self.assignments
        )
        return self._bumped(assignments=releases)

    def with_drain(self, *, host_id: str, reason: str, at: str) -> DesiredState:
        host = self.host(host_id)
        if host.state is not HostState.ACTIVE:
            raise ModelError(f"drain refused: host is {host.state.value}")
        drain = Drain(host_id=host_id, reason=reason, requested_at=at)
        return self._bumped(
            hosts=self._with_host(host_id, state=HostState.DRAINING),
            drains=self.drains + (drain,),
        )

    def with_drain_complete(self, *, host_id: str, at: str) -> DesiredState:
        host = self.host(host_id)
        if host.state is not HostState.DRAINING:
            raise ModelError(f"drain completion refused: host is {host.state.value}")
        outstanding = self.capacity(host_id).in_use
        if outstanding:
            raise ModelError(
                f"drain completion refused: {outstanding} assignment(s) still on the host"
            )
        drains = tuple(
            replace(item, state=DrainState.DRAINED, completed_at=at)
            if item.host_id == host_id and item.state is DrainState.DRAINING
            else item
            for item in self.drains
        )
        return self._bumped(
            hosts=self._with_host(host_id, state=HostState.DRAINED), drains=drains
        )

    def with_host_returned(self, *, host_id: str, at: str) -> DesiredState:
        host = self.host(host_id)
        if host.state is not HostState.DRAINED:
            raise ModelError(f"return refused: host is {host.state.value}")
        drains = tuple(
            replace(item, state=DrainState.ENDED, ended_at=at)
            if item.host_id == host_id and item.state is DrainState.DRAINED
            else item
            for item in self.drains
        )
        return self._bumped(
            hosts=self._with_host(host_id, state=HostState.ACTIVE), drains=drains
        )

    def with_rollout(
        self, *, rollout_id: str, pool_id: str, to_image_digest: str, at: str
    ) -> DesiredState:
        pool = self.pool(pool_id)
        _digest(to_image_digest, "rollout.to_image_digest")
        if to_image_digest == pool.image_digest:
            raise ModelError("rollout refused: the pool already runs that image")
        rollout = Rollout(
            rollout_id=rollout_id,
            pool_id=pool_id,
            from_image_digest=pool.image_digest,
            to_image_digest=to_image_digest,
            started_at=at,
        )
        updated = pool.with_image(to_image_digest, rollback_image_digest=pool.image_digest)
        return self._bumped(
            pools=self._with_pool(pool_id, **{
                "revision": updated.revision,
                "image_digest": updated.image_digest,
                "rollback_image_digest": updated.rollback_image_digest,
            }),
            rollouts=self.rollouts + (rollout,),
        )


def _typed(items: Sequence, kind: type, where: str) -> None:
    if not isinstance(items, tuple):
        raise ModelError(f"{where}: must be a tuple of {kind.__name__}")
    for index, item in enumerate(items):
        if not isinstance(item, kind):
            raise ModelError(f"{where}[{index}]: must be a {kind.__name__}, not {type(item).__name__}")


def _unique(items: Sequence, attribute: str, where: str) -> None:
    seen: set[str] = set()
    for item in items:
        value = getattr(item, attribute)
        if value in seen:
            raise ModelError(f"{where}: duplicate {attribute} {value}")
        seen.add(value)
