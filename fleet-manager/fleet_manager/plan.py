# spec: fleet-002-01
"""Plans: what an apply would do, computed before anything is done (FLEET-002).

A plan is a deterministic value. Given a base revision and an ordered list of
changes, its id is a digest of exactly those two things — so two callers who
plan the same work against the same revision agree on the id, and a plan that
has been edited after planning no longer matches its own id.

Planning *simulates* every change against a working copy of the state, so an
impossible change is refused at plan time with its index and the reason, rather
than discovered halfway through an apply. The simulation runs at the newest
timestamp already in the state (`plan_clock`), not at the wall clock: a plan
must be reproducible, and a plan that stamped itself with "now" would also let
a release be simulated *before* the assignment it releases. Apply is the
authority on time (`apply.py`), and it revalidates against the real state.

Capacity impact is computed per host from the simulated state, not asserted.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Iterator, Sequence

from .model import DesiredState, ModelError, _instant

# A state with no timestamps still needs a clock for its first simulated change.
PLAN_CLOCK_FLOOR = "1970-01-01T00:00:00+00:00"


class PlanError(ValueError):
    """A plan that cannot be built. Names the change index and the reason."""


class ChangeKind(str, Enum):
    ASSIGN = "assign"
    RELEASE = "release"
    DRAIN = "drain"
    COMPLETE_DRAIN = "complete_drain"
    RETURN_TO_SERVICE = "return_to_service"
    ROLLOUT = "rollout"


# A change is destructive when it ends, moves or replaces running work. Those
# require an explicitly authorized apply (FLEET-002) — see auth.Scope.FLEET_ADMIN.
DESTRUCTIVE = frozenset(
    {
        ChangeKind.RELEASE,
        ChangeKind.DRAIN,
        ChangeKind.COMPLETE_DRAIN,
        ChangeKind.ROLLOUT,
    }
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Change:
    """One intended operation. Parameters are strings so the digest is stable."""

    kind: ChangeKind
    subject: str
    parameters: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ChangeKind):
            options = ", ".join(kind.value for kind in ChangeKind)
            raise PlanError(f"change.kind: must be one of {options}")
        if not isinstance(self.subject, str) or not self.subject:
            raise PlanError("change.subject: must be a non-empty string")
        if not isinstance(self.parameters, tuple):
            raise PlanError("change.parameters: must be a tuple of (name, value) pairs")
        seen = set()
        for name, value in self.parameters:
            if not isinstance(name, str) or not name or not isinstance(value, str):
                raise PlanError("change.parameters: names and values must be strings")
            if name in seen:
                raise PlanError(f"change.parameters: duplicate name {name}")
            seen.add(name)

    @property
    def destructive(self) -> bool:
        return self.kind in DESTRUCTIVE

    def parameter(self, name: str) -> str:
        for key, value in self.parameters:
            if key == name:
                return value
        raise PlanError(f"change.parameters: {self.kind.value} needs {name}")

    def document(self) -> dict:
        return {
            "kind": self.kind.value,
            "subject": self.subject,
            "parameters": {name: value for name, value in self.parameters},
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class CapacityImpact:
    """What a plan does to one host's free slots."""

    host_id: str
    before_free: int
    after_free: int

    @property
    def delta(self) -> int:
        return self.after_free - self.before_free


@dataclass(frozen=True, slots=True, kw_only=True)
class Plan:
    plan_id: str
    base_revision: int
    changes: tuple[Change, ...]
    impacts: tuple[CapacityImpact, ...]
    resulting_revision: int

    def __post_init__(self) -> None:
        if not self.changes:
            raise PlanError("plan: at least one change is required")
        if not all(isinstance(change, Change) for change in self.changes):
            raise PlanError("plan: every change must be a Change")
        expected = plan_id_for(self.base_revision, self.changes)
        if self.plan_id != expected:
            raise PlanError(
                "plan.plan_id: does not match its base revision and changes "
                "(a plan is not editable after it is built)"
            )
        if self.resulting_revision != self.base_revision + len(self.changes):
            raise PlanError(
                "plan.resulting_revision: must be the base revision plus one per change"
            )

    @property
    def destructive(self) -> bool:
        return any(change.destructive for change in self.changes)

    def document(self) -> dict:
        return {
            "schema": "fleet-manager-plan/1",
            "plan_id": self.plan_id,
            "base_revision": self.base_revision,
            "resulting_revision": self.resulting_revision,
            "destructive": self.destructive,
            "changes": [change.document() for change in self.changes],
            "capacity_impact": [
                {
                    "host_id": impact.host_id,
                    "before_free": impact.before_free,
                    "after_free": impact.after_free,
                }
                for impact in self.impacts
            ],
        }


def plan_id_for(base_revision: int, changes: Sequence[Change]) -> str:
    """A stable digest of (base revision, ordered changes)."""
    payload = {
        "base_revision": base_revision,
        "changes": [change.document() for change in changes],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "plan:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def build_plan(state: DesiredState, changes: Sequence[Change]) -> Plan:
    """Simulate every change against `state` and describe the result."""
    ordered = tuple(changes)
    if not ordered:
        raise PlanError("plan: at least one change is required")

    working = state
    first_before: dict[str, int] = {}
    last_after: dict[str, int] = {}

    for index, change in enumerate(ordered):
        if not isinstance(change, Change):
            raise PlanError(f"plan: change {index} is not a Change")
        try:
            following = simulate(working, change)
        except ModelError as exc:
            raise PlanError(
                f"plan: change {index} ({change.kind.value}) is not possible: {exc}"
            ) from None
        except PlanError as exc:
            raise PlanError(
                f"plan: change {index} ({change.kind.value}) is malformed: {exc}"
            ) from None
        host_id = _host_of(change)
        if host_id is None and change.kind is ChangeKind.RELEASE:
            # A release names only the assignment; the host comes from the state
            # it was issued against. Simulate succeeded, so the lookup is safe.
            host_id = working.assignment(change.subject).host_id
        if host_id is not None:
            first_before.setdefault(host_id, _free(working, host_id))
            last_after[host_id] = _free(following, host_id)
        working = following

    impacts = tuple(
        CapacityImpact(
            host_id=host_id,
            before_free=first_before[host_id],
            after_free=last_after.get(host_id, first_before[host_id]),
        )
        for host_id in sorted(first_before)
    )
    return Plan(
        plan_id=plan_id_for(state.revision, ordered),
        base_revision=state.revision,
        changes=ordered,
        impacts=impacts,
        resulting_revision=state.revision + len(ordered),
    )


def plan_clock(state: DesiredState) -> str:
    """The newest instant the state already carries, or the floor if it has none.

    Derived from the state, never from the wall clock: two planners reading the
    same revision must simulate the same plan, and a transition may not be
    simulated before the work it acts on.
    """
    instants = [_instant(value, "plan_clock") for value in _state_timestamps(state)]
    if not instants:
        return PLAN_CLOCK_FLOOR
    newest: datetime = max(instants)
    return newest.isoformat()


def _state_timestamps(state: DesiredState) -> Iterator[str]:
    for assignment in state.assignments:
        yield assignment.issued_at
        if assignment.released_at is not None:
            yield assignment.released_at
    for drain in state.drains:
        yield drain.requested_at
        if drain.completed_at is not None:
            yield drain.completed_at
        if drain.ended_at is not None:
            yield drain.ended_at
    for rollout in state.rollouts:
        yield rollout.started_at


def simulate(
    state: DesiredState, change: Change, *, at: str | None = None
) -> DesiredState:
    """Apply one change to a working copy, at `at` (the state's clock when planning)."""
    if at is None:
        at = plan_clock(state)
    kind = change.kind
    if kind is ChangeKind.ASSIGN:
        return state.with_assignment(
            assignment_id=change.parameter("assignment_id"),
            request_id=change.parameter("request_id"),
            pool_id=change.parameter("pool_id"),
            host_id=change.parameter("host_id"),
            at=at,
        )
    if kind is ChangeKind.RELEASE:
        return state.with_release(assignment_id=change.subject, at=at)
    if kind is ChangeKind.DRAIN:
        return state.with_drain(
            host_id=change.subject, reason=change.parameter("reason"), at=at
        )
    if kind is ChangeKind.COMPLETE_DRAIN:
        return state.with_drain_complete(host_id=change.subject, at=at)
    if kind is ChangeKind.RETURN_TO_SERVICE:
        return state.with_host_returned(host_id=change.subject, at=at)
    if kind is ChangeKind.ROLLOUT:
        return state.with_rollout(
            rollout_id=change.parameter("rollout_id"),
            pool_id=change.subject,
            to_image_digest=change.parameter("to_image_digest"),
            at=at,
        )
    raise PlanError(f"plan: unhandled change kind {kind}")


def _host_of(change: Change) -> str | None:
    if change.kind is ChangeKind.ASSIGN:
        return change.parameter("host_id")
    if change.kind in {
        ChangeKind.DRAIN,
        ChangeKind.COMPLETE_DRAIN,
        ChangeKind.RETURN_TO_SERVICE,
    }:
        return change.subject
    if change.kind is ChangeKind.ROLLOUT:
        # A rollout moves an image, not a slot.
        return None
    return None


def _free(state: DesiredState, host_id: str) -> int:
    try:
        return state.capacity(host_id).free
    except ModelError:
        return 0
