# spec: fleet-003-01, fleet-003-02, fleet-003-03, fleet-003-04
"""Reconciliation: desired versus observed, as a bounded diff (FLEET-003, 2.3).

A comparison returns a diff, never a state (`observation.py` says so at the top
of that module, and this is the module it was talking about). `reconcile()`
reads one `DesiredState` revision and one report per host, and returns a
`Reconciliation`: an ordered list of drifts it found, an ordered list of
`Change` values it would submit, and the work it deliberately did *not* submit
with the reason. Nothing here mutates a runner, opens a socket, or produces a
new revision — `apply.apply_plan()` remains the only path to one, and the
changes this module emits are the same `Change` values `plan.build_plan()`
takes, so a reconciliation is carried out the same way an operator's plan is.

Three rules shape the diff, and each exists because of the failure it prevents:

- **Bounded convergence (fleet-003-02).** A reconciler that tries to fix
  everything at once turns one incident into a fleet-wide one. Every proposed
  change is charged against a `ConvergenceLimits` cap (drains, replacements,
  host mutations) and against the affected pool's `DisruptionBudget`; what does
  not fit is *deferred with its reason*, never dropped. A cap of zero is how a
  halted reconciler is expressed: it emits nothing and still returns the diff.
- **Leave running jobs untouched (fleet-003-03).** The reconciler never emits a
  destructive change against work it cannot prove is finished. A host that
  reports a runner does not get its drain completed; a host that has not
  reported at all gets no new assignment; a runner the desired state does not
  account for is reported as unmanaged and left alone. The join between
  desired assignments and observed runners is by (host, pool) *count*, because
  a runner id is the host's and an assignment id is the manager's; pretending
  they are the same key would invent an identity the contracts do not carry.
- **Determinism (fleet-003-01).** The same revision and the same reports
  produce the same reconciliation, down to its id, which is a digest of exactly
  those inputs plus the limits. Ordering is a total order over (kind, host,
  pool), never dictionary or set iteration order, so a fixture can assert the
  whole document byte for byte.

Reconciliation is count-based and revision-based; it has no staleness policy
for observations and no runtime contact. Both are named limits in the QA record.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence

from .model import (
    AssignmentState,
    DesiredState,
    DrainState,
    HostState,
    ModelError,
    _identifier,
)
from .observation import Observation, ObservationError, ObservedRunner
from .plan import Change, ChangeKind, simulate

RECONCILIATION_SCHEMA = "fleet-manager-reconciliation/1"

# A candidate's position in the batch. Finishing a disruption already in
# motion before starting a new one is the conservative order: a drain that is
# one release away from completing should complete, not wait behind an
# assignment.
_CANDIDATE_ORDER = {
    ChangeKind.COMPLETE_DRAIN: 0,
    ChangeKind.RETURN_TO_SERVICE: 1,
    ChangeKind.DRAIN: 2,
    ChangeKind.RELEASE: 3,
    ChangeKind.ROLLOUT: 4,
    ChangeKind.ASSIGN: 5,
}


class ReconcileError(ValueError):
    """A reconciliation that cannot be computed. Names the input at fault."""


class DriftKind(str, Enum):
    WARM_SHORTFALL = "warm_shortfall"
    UNMANAGED_RUNNER = "unmanaged_runner"
    UNKNOWN_HOST = "unknown_host"
    HOST_NOT_REPORTING = "host_not_reporting"
    DRAIN_COMPLETABLE = "drain_completable"
    DRAIN_BLOCKED = "drain_blocked"


@dataclass(frozen=True, slots=True, kw_only=True)
class Drift:
    """One difference between desired and observed, and how much of it there is.

    A drift is a finding, not an instruction: most drifts produce no change at
    all, and the ones that do produce it through `reconcile()`'s candidate list.
    """

    kind: DriftKind
    host_id: str | None = None
    pool_id: str | None = None
    count: int = 0
    reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.kind, DriftKind):
            options = ", ".join(kind.value for kind in DriftKind)
            raise ReconcileError(f"drift.kind: must be one of {options}")
        if self.host_id is not None:
            _identifier(self.host_id, "drift.host_id")
        if self.pool_id is not None:
            _identifier(self.pool_id, "drift.pool_id")
        if not isinstance(self.count, int) or isinstance(self.count, bool) or self.count < 0:
            raise ReconcileError("drift.count: must be an integer >= 0")
        if not isinstance(self.reason, str):
            raise ReconcileError("drift.reason: must be a string")

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.kind.value, self.host_id or "", self.pool_id or "")

    def document(self) -> dict:
        return {
            "kind": self.kind.value,
            "host_id": self.host_id,
            "pool_id": self.pool_id,
            "count": self.count,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class ConvergenceLimits:
    """How much convergence one reconciliation may attempt at once (FLEET-003).

    Zero is a meaningful value: it is how "stop unsafe new mutations" is said
    in data. Every cap counts changes *this batch* would submit, not changes
    already in flight.
    """

    max_drains: int = 1
    max_replacements: int = 1
    max_host_mutations: int = 1

    def __post_init__(self) -> None:
        for name in ("max_drains", "max_replacements", "max_host_mutations"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ReconcileError(f"convergence_limits.{name}: must be an integer >= 0")

    def document(self) -> dict:
        return {
            "max_drains": self.max_drains,
            "max_replacements": self.max_replacements,
            "max_host_mutations": self.max_host_mutations,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class Deferred:
    """A change the reconciler would submit, and why it did not."""

    change: Change
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.change, Change):
            raise ReconcileError("deferred.change: must be a Change")
        if not isinstance(self.reason, str) or not self.reason:
            raise ReconcileError("deferred.reason: must be a non-empty string")

    def document(self) -> dict:
        return {"change": self.change.document(), "reason": self.reason}


@dataclass(frozen=True, slots=True, kw_only=True)
class Reconciliation:
    """One complete diff. Recomputes its id, so it cannot be edited either."""

    reconciliation_id: str
    base_revision: int
    observations: tuple[Observation, ...]
    limits: ConvergenceLimits
    halted: bool
    drifts: tuple[Drift, ...]
    candidates: tuple[Change, ...]
    changes: tuple[Change, ...]
    deferred: tuple[Deferred, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.base_revision, int) or isinstance(self.base_revision, bool):
            raise ReconcileError("reconciliation.base_revision: must be an integer")
        if not isinstance(self.observations, tuple):
            raise ReconcileError("reconciliation.observations: must be a tuple")
        for index, observation in enumerate(self.observations):
            if not isinstance(observation, Observation):
                raise ReconcileError(
                    f"reconciliation.observations[{index}]: must be an Observation"
                )
        hosts = [observation.host_id for observation in self.observations]
        if len(set(hosts)) != len(hosts):
            raise ReconcileError(
                "reconciliation.observations: two reports for one host "
                "(which report is newer is not something this layer guesses)"
            )
        if not isinstance(self.limits, ConvergenceLimits):
            raise ReconcileError("reconciliation.limits: must be ConvergenceLimits")
        if not isinstance(self.halted, bool):
            raise ReconcileError("reconciliation.halted: must be a boolean")
        if not all(isinstance(drift, Drift) for drift in self.drifts):
            raise ReconcileError("reconciliation.drifts: must be Drift values")
        ordered = tuple(sorted(self.drifts, key=lambda drift: drift.key))
        if ordered != self.drifts:
            raise ReconcileError(
                "reconciliation.drifts: must be in (kind, host, pool) order "
                "(a diff whose order depends on iteration makes a fixture useless)"
            )
        for name in ("candidates", "changes"):
            items = getattr(self, name)
            if not isinstance(items, tuple) or not all(
                isinstance(item, Change) for item in items
            ):
                raise ReconcileError(f"reconciliation.{name}: must be Change values")
        if not all(isinstance(item, Deferred) for item in self.deferred):
            raise ReconcileError("reconciliation.deferred: must be Deferred values")
        deferred_changes = {item.change for item in self.deferred}
        kept = tuple(
            change for change in self.candidates if change not in deferred_changes
        )
        if kept != self.changes:
            raise ReconcileError(
                "reconciliation.changes: must be the candidates that were not "
                "deferred, in candidate order"
            )
        if len(self.changes) + len(self.deferred) != len(self.candidates):
            raise ReconcileError(
                "reconciliation.candidates: every candidate is either submitted "
                "or deferred, never both and never neither"
            )
        expected = reconciliation_id_for(
            self.base_revision, self.observations, self.limits, self.halted
        )
        if self.reconciliation_id != expected:
            raise ReconcileError(
                "reconciliation.reconciliation_id: does not match its revision, "
                "observations, limits and halt state"
            )

    @property
    def converged(self) -> bool:
        return not self.changes and not self.deferred

    def document(self) -> dict:
        return {
            "schema": RECONCILIATION_SCHEMA,
            "reconciliation_id": self.reconciliation_id,
            "base_revision": self.base_revision,
            "halted": self.halted,
            "limits": self.limits.document(),
            "observations": [
                observation_to_document(observation) for observation in self.observations
            ],
            "drifts": [drift.document() for drift in self.drifts],
            "candidates": [change.document() for change in self.candidates],
            "changes": [change.document() for change in self.changes],
            "deferred": [item.document() for item in self.deferred],
            "converged": self.converged,
        }


def reconciliation_id_for(
    base_revision: int,
    observations: Sequence[Observation],
    limits: ConvergenceLimits,
    halted: bool,
) -> str:
    """A stable digest of (revision, reports, limits, halt state)."""
    payload = {
        "base_revision": base_revision,
        "observations": [
            observation_to_document(observation) for observation in observations
        ],
        "limits": limits.document(),
        "halted": halted,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "reconciliation:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def reconcile(
    state: DesiredState,
    observations: Iterable[Observation],
    *,
    limits: ConvergenceLimits | None = None,
    halted: bool = False,
) -> Reconciliation:
    """Diff `state` against `observations` and bound what may be submitted."""
    if not isinstance(state, DesiredState):
        raise ReconcileError("reconcile.state: must be a DesiredState")
    limits = ConvergenceLimits() if limits is None else limits
    if not isinstance(limits, ConvergenceLimits):
        raise ReconcileError("reconcile.limits: must be ConvergenceLimits")
    if not isinstance(halted, bool):
        raise ReconcileError("reconcile.halted: must be a boolean")
    reports = tuple(sorted(observations, key=lambda item: item.host_id))
    for index, report in enumerate(reports):
        if not isinstance(report, Observation):
            raise ReconcileError(f"reconcile.observations[{index}]: must be an Observation")

    by_host = {report.host_id: report for report in reports}
    if len(by_host) != len(reports):
        raise ReconcileError(
            "reconcile.observations: two reports for one host "
            "(which report is newer is not something this layer guesses)"
        )

    drifts: list[Drift] = []
    candidates: list[Change] = []

    for report in reports:
        if report.host_id not in {host.host_id for host in state.hosts}:
            drifts.append(
                Drift(
                    kind=DriftKind.UNKNOWN_HOST,
                    host_id=report.host_id,
                    reason="host is not in the desired state; it is not adopted",
                )
            )

    active = {host.host_id for host in state.hosts if host.state is HostState.ACTIVE}
    for host in sorted(state.hosts, key=lambda item: item.host_id):
        if host.state is HostState.ACTIVE and host.host_id not in by_host:
            drifts.append(
                Drift(
                    kind=DriftKind.HOST_NOT_REPORTING,
                    host_id=host.host_id,
                    reason="no observation for an active host; it gets no new assignment",
                )
            )

    # Desired and observed counts per (host, pool). Both sides are counted, not
    # matched by id: a runner id belongs to the host and an assignment id to the
    # manager, so a join on ids would be a join on nothing.
    assigned: dict[tuple[str, str], int] = {}
    for assignment in state.assignments:
        if assignment.state is AssignmentState.ASSIGNED:
            key = (assignment.host_id, assignment.pool_id)
            assigned[key] = assigned.get(key, 0) + 1
    observed: dict[tuple[str, str], int] = {}
    for report in reports:
        for runner in report.runners:
            key = (report.host_id, runner.pool_id)
            observed[key] = observed.get(key, 0) + 1

    for (host_id, pool_id) in sorted(observed):
        if host_id not in {host.host_id for host in state.hosts}:
            continue  # already reported as an unknown host; never acted on
        if host_id not in active:
            continue  # a draining host's runners are covered by drain_blocked
        surplus = observed[(host_id, pool_id)] - assigned.get((host_id, pool_id), 0)
        if surplus > 0:
            drifts.append(
                Drift(
                    kind=DriftKind.UNMANAGED_RUNNER,
                    host_id=host_id,
                    pool_id=pool_id,
                    count=surplus,
                    reason="runner is not accounted for by an assignment; left alone",
                )
            )

    # Warm floor, per pool, against what active reporting hosts actually run.
    working = state
    for pool in sorted(state.pools, key=lambda item: item.pool_id):
        warm = sum(
            count
            for (host_id, pool_id), count in observed.items()
            if pool_id == pool.pool_id and host_id in active
        )
        missing = pool.warm_min - warm
        if missing <= 0:
            continue
        drifts.append(
            Drift(
                kind=DriftKind.WARM_SHORTFALL,
                pool_id=pool.pool_id,
                count=missing,
                reason=f"observed {warm} runner(s) for a warm floor of {pool.warm_min}",
            )
        )
        taken = {assignment.assignment_id for assignment in state.assignments}
        for _ in range(missing):
            host = _placement_host(
                working, state, pool.pool_id, reports=by_host, active=active
            )
            if host is None:
                break
            assignment_id = _free_assignment_id(pool.pool_id, taken)
            change = Change(
                kind=ChangeKind.ASSIGN,
                subject=assignment_id,
                parameters=(
                    ("assignment_id", assignment_id),
                    # A reconciler-placed assignment answers no core request, so
                    # its request id names the reconciler and the slot, not a caller.
                    ("request_id", assignment_id.replace("rec.", "reconcile.")),
                    ("pool_id", pool.pool_id),
                    ("host_id", host),
                ),
            )
            taken.add(assignment_id)
            candidates.append(change)
            working = simulate(working, change)

    for drain in state.drains:
        if drain.state is not DrainState.DRAINING:
            continue
        host = state.host(drain.host_id)
        in_use = state.capacity(drain.host_id).in_use
        report = by_host.get(drain.host_id)
        running = 0 if report is None else report.runner_count
        if in_use or running:
            drifts.append(
                Drift(
                    kind=DriftKind.DRAIN_BLOCKED,
                    host_id=drain.host_id,
                    count=in_use + running,
                    reason=(
                        f"{in_use} assignment(s) and {running} observed runner(s) "
                        "remain; the drain is not completed"
                    ),
                )
            )
            continue
        drifts.append(
            Drift(
                kind=DriftKind.DRAIN_COMPLETABLE,
                host_id=host.host_id,
                reason="no assignment and no observed runner remains",
            )
        )
        candidates.append(Change(kind=ChangeKind.COMPLETE_DRAIN, subject=host.host_id))

    # One total order for the whole batch, before anything is charged: the
    # documented order is also the order work is submitted in, and a candidate
    # list built per-pool would otherwise disagree with it (a drain is found
    # after every pool, so without this sort it would be charged last while
    # being submitted first).
    candidates = sorted(candidates, key=_candidate_key)
    changes, deferred = bound_candidates(state, candidates, limits=limits, halted=halted)
    return Reconciliation(
        reconciliation_id=reconciliation_id_for(state.revision, reports, limits, halted),
        base_revision=state.revision,
        observations=reports,
        limits=limits,
        halted=halted,
        drifts=tuple(sorted(drifts, key=lambda drift: drift.key)),
        candidates=tuple(candidates),
        changes=changes,
        deferred=deferred,
    )


def bound_candidates(
    state: DesiredState,
    candidates: Sequence[Change],
    *,
    limits: ConvergenceLimits | None = None,
    halted: bool = False,
) -> tuple[tuple[Change, ...], tuple[Deferred, ...]]:
    """Split candidates into what may be submitted now and what waits, and why (FLEET-003).

    Public because it is the whole of "bounded convergence": a later sprint that
    proposes drains and replacements uses this unchanged, and a test can drive
    each cap with the change kind it names.
    """
    limits = ConvergenceLimits() if limits is None else limits
    if not isinstance(limits, ConvergenceLimits):
        raise ReconcileError("bound_candidates.limits: must be ConvergenceLimits")
    if not isinstance(halted, bool):
        raise ReconcileError("bound_candidates.halted: must be a boolean")
    if not isinstance(state, DesiredState):
        raise ReconcileError("bound_candidates.state: must be a DesiredState")

    ordered = _validated_candidates(candidates)
    submitted: list[Change] = []
    deferred: list[Deferred] = []
    used = {"drains": 0, "replacements": 0, "host_mutations": 0}
    per_pool: dict[str, int] = {}

    for change in ordered:
        reason = _exhausted(state, change, used, per_pool, limits, halted)
        if reason is not None:
            deferred.append(Deferred(change=change, reason=reason))
            continue
        submitted.append(change)
        _charge(state, change, used, per_pool)
    return tuple(submitted), tuple(deferred)


# --- internals -------------------------------------------------------------


# The parameters each kind needs before it can be charged or simulated. Checked
# up front so a malformed candidate is named with its index rather than failing
# later inside a sort key.
_REQUIRED_PARAMETERS = {
    ChangeKind.ASSIGN: ("assignment_id", "request_id", "pool_id", "host_id"),
    ChangeKind.DRAIN: ("reason",),
    ChangeKind.ROLLOUT: ("rollout_id", "to_image_digest"),
}


def _validated_candidates(candidates: Sequence[Change]) -> tuple[Change, ...]:
    if isinstance(candidates, (str, bytes)) or not isinstance(candidates, Sequence):
        raise ReconcileError("bound_candidates.candidates: must be a list of Change values")
    checked = []
    for index, change in enumerate(candidates):
        if not isinstance(change, Change):
            raise ReconcileError(
                f"bound_candidates.candidates[{index}]: must be a Change"
            )
        names = {name for name, _ in change.parameters}
        for name in _REQUIRED_PARAMETERS.get(change.kind, ()):
            if name not in names:
                raise ReconcileError(
                    f"bound_candidates.candidates[{index}]: "
                    f"{change.kind.value} needs {name}"
                )
        checked.append(change)
    return tuple(sorted(checked, key=_candidate_key))


def _candidate_key(change: Change) -> tuple:
    parameters = tuple(sorted(change.parameters))
    return (
        _CANDIDATE_ORDER.get(change.kind, len(_CANDIDATE_ORDER)),
        change.subject,
        parameters,
    )


def _host_of(change: Change) -> str | None:
    if change.kind is ChangeKind.ASSIGN:
        return change.parameter("host_id")
    if change.kind in {
        ChangeKind.DRAIN,
        ChangeKind.COMPLETE_DRAIN,
        ChangeKind.RETURN_TO_SERVICE,
    }:
        return change.subject
    return None


def _disrupted_pools(state: DesiredState, change: Change) -> tuple[str, ...]:
    try:
        if change.kind is ChangeKind.ASSIGN:
            return (change.parameter("pool_id"),)
        if change.kind is ChangeKind.RELEASE:
            return (state.assignment(change.subject).pool_id,)
        if change.kind is ChangeKind.ROLLOUT:
            return (change.subject,)
        if change.kind in {
            ChangeKind.DRAIN,
            ChangeKind.COMPLETE_DRAIN,
            ChangeKind.RETURN_TO_SERVICE,
        }:
            return state.host(change.subject).allowed_pools
    except (ModelError, ValueError):
        return ()
    return ()


def _budget(state: DesiredState, pool_id: str) -> int | None:
    for pool in state.pools:
        if pool.pool_id == pool_id:
            return pool.disruption_budget.max_parallel
    return None


def _exhausted(
    state: DesiredState,
    change: Change,
    used: dict[str, int],
    per_pool: dict[str, int],
    limits: ConvergenceLimits,
    halted: bool,
) -> str | None:
    if halted:
        return "the reconciler is halted; no new mutation is submitted"
    if change.kind in {ChangeKind.DRAIN, ChangeKind.COMPLETE_DRAIN}:
        if used["drains"] >= limits.max_drains:
            return f"the drain cap ({limits.max_drains}) is used by this batch"
    if change.kind is ChangeKind.ROLLOUT:
        if used["replacements"] >= limits.max_replacements:
            return f"the replacement cap ({limits.max_replacements}) is used by this batch"
    if _host_of(change) is not None:
        if used["host_mutations"] >= limits.max_host_mutations:
            return (
                f"the host-mutation cap ({limits.max_host_mutations}) is used "
                "by this batch"
            )
    if change.destructive:
        for pool_id in _disrupted_pools(state, change):
            budget = _budget(state, pool_id)
            if budget is not None and per_pool.get(pool_id, 0) >= budget:
                return (
                    f"pool {pool_id} disruption budget ({budget}) is used by "
                    "this batch"
                )
    return None


def _charge(
    state: DesiredState,
    change: Change,
    used: dict[str, int],
    per_pool: dict[str, int],
) -> None:
    if change.kind in {ChangeKind.DRAIN, ChangeKind.COMPLETE_DRAIN}:
        used["drains"] += 1
    if change.kind is ChangeKind.ROLLOUT:
        used["replacements"] += 1
    if _host_of(change) is not None:
        used["host_mutations"] += 1
    if change.destructive:
        for pool_id in _disrupted_pools(state, change):
            per_pool[pool_id] = per_pool.get(pool_id, 0) + 1


def _free_assignment_id(pool_id: str, taken: set[str]) -> str:
    index = 1
    while True:
        candidate = f"rec.{pool_id}.{index}"
        if candidate not in taken:
            return candidate
        index += 1


def _placement_host(
    working: DesiredState,
    state: DesiredState,
    pool_id: str,
    *,
    reports: dict[str, Observation],
    active: set[str],
) -> str | None:
    """The host a new assignment goes to: most free slots, then lowest id.

    A host that has not reported is not offered: placing work on a host whose
    state is unknown is how a reconciler creates load it cannot see.
    """
    pool = state.pool(pool_id)
    best: tuple[int, str] | None = None
    for host in sorted(state.hosts, key=lambda item: item.host_id):
        if host.host_id not in active or host.host_id not in reports:
            continue
        if host.refusal_for(pool) is not None:
            continue
        free = working.capacity(host.host_id).free
        if free <= 0:
            continue
        rank = (-free, host.host_id)
        if best is None or rank < best:
            best = rank
    return None if best is None else best[1]


# --- observation documents -------------------------------------------------


def observation_to_document(observation: Observation) -> dict:
    if not isinstance(observation, Observation):
        raise ReconcileError("observation_to_document: must be an Observation")
    return {
        "host_id": observation.host_id,
        "observed_at": observation.observed_at,
        "agent_version": observation.agent_version,
        "runners": [
            {
                "runner_id": runner.runner_id,
                "pool_id": runner.pool_id,
                "started_at": runner.started_at,
                "job_id": runner.job_id,
            }
            for runner in observation.runners
        ],
    }


def observation_from_document(doc: object, where: str = "observation") -> Observation:
    """Parse one host report. Closed shape: a missing field is named, an extra one refused."""
    if not isinstance(doc, dict):
        raise ReconcileError(f"{where}: must be an object")
    required = ("host_id", "observed_at", "runners")
    optional = ("agent_version",)
    for name in required:
        if name not in doc:
            raise ReconcileError(f"{where}.{name}: is required")
    for name in doc:
        if name not in required and name not in optional:
            raise ReconcileError(f"{where}.{name}: is not a field of an observation")
    runners = doc["runners"]
    if not isinstance(runners, list):
        raise ReconcileError(f"{where}.runners: must be a list")
    parsed = []
    for index, runner in enumerate(runners):
        at = f"{where}.runners[{index}]"
        if not isinstance(runner, dict):
            raise ReconcileError(f"{at}: must be an object")
        for name in ("runner_id", "pool_id", "started_at"):
            if name not in runner:
                raise ReconcileError(f"{at}.{name}: is required")
        for name in runner:
            if name not in ("runner_id", "pool_id", "started_at", "job_id"):
                raise ReconcileError(f"{at}.{name}: is not a field of a runner")
        try:
            parsed.append(
                ObservedRunner(
                    runner_id=runner["runner_id"],
                    pool_id=runner["pool_id"],
                    started_at=runner["started_at"],
                    job_id=runner.get("job_id"),
                )
            )
        except ObservationError as exc:
            raise ReconcileError(f"{at}: {exc}") from None
    try:
        return Observation(
            host_id=doc["host_id"],
            observed_at=doc["observed_at"],
            runners=tuple(parsed),
            agent_version=doc.get("agent_version"),
        )
    except ObservationError as exc:
        raise ReconcileError(f"{where}: {exc}") from None
