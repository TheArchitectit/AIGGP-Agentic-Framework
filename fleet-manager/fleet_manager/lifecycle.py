# spec: fleet-008-01, fleet-008-02, fleet-008-03, fleet-008-04, fleet-008-05
"""One job per instance: the lifecycle, clean-by-proof, and quarantine.

RUN-001 puts the property in one sentence — a registered runner instance
accepts at most one job and is destroyed after completion, timeout,
cancellation, or uncertain disconnect, and a warm pool must not keep a
previously used job filesystem. RUN-002 puts the cost of getting it wrong in
the next: a replacement shall not join capacity until the previous instance's
cleanup is proven or its resources are quarantined.

`adapters` says what an instance *is*; this module says what happens to it.
Nothing here runs a process either — the disposal results and timestamps are
values this module validates, not observations it collects. Producing them from
a host is the next box.

Layering: this module imports `adapters` (and `channel` for one timestamp
rule), never the other way round, so the value layer stays independent of the
lifecycle layer.

Refusals here are `AdapterError` with a kind, not `AdapterContractError`.
`adapters` raises the contract error for a shape it will not build; a lifecycle
refusal is a fleet decision (a policy denial, an inadmissible proof), and
fleet-008-05 requires each one to name its kind rather than a ninth spelling.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum

from .adapters import (
    AdapterContractError,
    AdapterError,
    ErrorKind,
    WarmInstance,
    WarmPool,
    _digest,
    _identifier_checked,
)
from .channel import ChannelError, _timestamp

__all__ = [
    "AdmissionGate",
    "CleanupEvidence",
    "Disposal",
    "JobLifecycle",
    "JobState",
    "Quarantine",
    "TERMINAL_JOB_STATES",
    "admit_replacement",
    "next_states",
]

_MAX_REASON = 512


class Disposal(str, Enum):
    """What happened to one kind of resource an instance owned.

    `ABSENT` is not a weaker `DISPOSED`: an instance that never created a
    volume or a network leaves nothing behind, and saying so is the difference
    between a proof and a claim.
    """

    DISPOSED = "disposed"
    ABSENT = "absent"
    FAILED = "failed"


def _disposal(value: object, where: str) -> Disposal:
    if not isinstance(value, Disposal):
        options = ", ".join(item.value for item in Disposal)
        raise AdapterError(
            ErrorKind.CLEANUP_FAILURE, f"{where}: must be one of {options}"
        )
    return value


def _instant(value: object, where: str) -> datetime:
    """An ISO-8601 instant carrying an offset.

    The rule lives in `channel` — a timestamp without an offset is refused
    rather than assumed — and is reused here rather than restated.
    """
    try:
        return _timestamp(value, where)
    except ChannelError as exc:
        raise AdapterError(ErrorKind.CLEANUP_FAILURE, str(exc)) from None


def _name_of(wanted: object) -> str:
    """A state's spelling for a refusal, whether or not it is a JobState."""

    return str(getattr(wanted, "value", None) or type(wanted).__name__)


def _identity(value: object, field: str, kind: ErrorKind) -> None:
    """The model's identifier rule, as this module's typed refusal."""

    try:
        _identifier_checked(value, field)
    except AdapterContractError as exc:
        raise AdapterError(kind, str(exc)) from None


def _digest_checked(value: object, field: str, kind: ErrorKind) -> None:
    try:
        _digest(value, field)
    except AdapterContractError as exc:
        raise AdapterError(kind, str(exc)) from None


@dataclass(frozen=True, slots=True, kw_only=True)
class CleanupEvidence:
    """RUN-002's five things about one instance, as one value.

    Every field except job identity is required, because a proof must not be
    able to leave a field out. Job identity is the one optional field because
    RUN-002 says "if known": an uncertain disconnect may never learn it, and
    requiring it would make that case impossible to prove clean.

    A disposal of `FAILED` is *recorded* rather than refused here — it is what
    happened, and hiding it would lose the reason the resources are not clean.
    It is refused where a proof is *used*: `admissible` is false.
    """

    instance_id: str | None = None
    image_digest: str | None = None
    volume_disposal: Disposal | None = None
    network_disposal: Disposal | None = None
    started_at: str | None = None
    finished_at: str | None = None
    job_id: str | None = None

    def __post_init__(self) -> None:
        for field, value in (
            ("instance_id", self.instance_id),
            ("image_digest", self.image_digest),
            ("volume_disposal", self.volume_disposal),
            ("network_disposal", self.network_disposal),
            ("started_at", self.started_at),
            ("finished_at", self.finished_at),
        ):
            if value is None:
                raise AdapterError(
                    _CLEANUP,
                    f"cleanup_evidence.{field}: is required — a proof missing "
                    "it is not a proof of cleanup",
                )
        _identity(self.instance_id, "cleanup_evidence.instance_id", _CLEANUP)
        _digest_checked(
            self.image_digest, "cleanup_evidence.image_digest", _CLEANUP
        )
        _disposal(self.volume_disposal, "cleanup_evidence.volume_disposal")
        _disposal(self.network_disposal, "cleanup_evidence.network_disposal")
        started = _instant(self.started_at, "cleanup_evidence.started_at")
        finished = _instant(self.finished_at, "cleanup_evidence.finished_at")
        if finished < started:
            raise AdapterError(
                _CLEANUP,
                "cleanup_evidence: finished_at precedes started_at — an "
                "interval that runs backwards is not evidence of a cleanup",
            )
        if self.job_id is not None:
            if not isinstance(self.job_id, str) or not self.job_id:
                raise AdapterError(
                    _CLEANUP,
                    "cleanup_evidence.job_id: must be omitted or a non-empty "
                    "string",
                )
            _identity(self.job_id, "cleanup_evidence.job_id", _CLEANUP)

    @property
    def admissible(self) -> bool:
        """Whether this is proof of cleanup.

        A disposal that failed is a record of what happened, not proof that
        the resources are gone — keeping the record is the point, admitting it
        as proof is the mistake.
        """

        return (
            self.volume_disposal is not Disposal.FAILED
            and self.network_disposal is not Disposal.FAILED
        )

    def document(self) -> dict:
        document = {
            "instance_id": self.instance_id,
            "image_digest": self.image_digest,
            "volume_disposal": self.volume_disposal.value,
            "network_disposal": self.network_disposal.value,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }
        if self.job_id is not None:
            document["job_id"] = self.job_id
        return document


@dataclass(frozen=True, slots=True, kw_only=True)
class Quarantine:
    """RUN-002's alternative to a proof: the resources are held, not reused.

    A quarantine nobody can inspect is a deletion with extra steps, so the
    value names the instance, the failure, and when.
    """

    instance_id: str | None = None
    failure_kind: str | None = None
    quarantined_at: str | None = None

    def __post_init__(self) -> None:
        for field, value in (
            ("instance_id", self.instance_id),
            ("failure_kind", self.failure_kind),
            ("quarantined_at", self.quarantined_at),
        ):
            if value is None:
                raise AdapterError(
                    _CLEANUP,
                    f"quarantine.{field}: is required — a quarantine that "
                    "cannot be inspected is a deletion",
                )
        _identity(self.instance_id, "quarantine.instance_id", _CLEANUP)
        if not isinstance(self.failure_kind, str) or not self.failure_kind:
            raise AdapterError(
                _CLEANUP, "quarantine.failure_kind: must name the failure"
            )
        if len(self.failure_kind) > _MAX_REASON:
            raise AdapterError(
                _CLEANUP,
                f"quarantine.failure_kind: exceeds {_MAX_REASON} characters",
            )
        _instant(self.quarantined_at, "quarantine.quarantined_at")

    def document(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "failure_kind": self.failure_kind,
            "quarantined_at": self.quarantined_at,
        }


class JobState(str, Enum):
    """The one-job machine, closed.

    A lifecycle with an open set of states is one that can be "restarted" by
    accident, so there is no transition out of a terminal state and none from a
    terminal state back to warm. `JobState` names the job, `InstanceState` names
    the container; `PREPULLED` appears in both because it is honestly both.
    """

    PREPULLED = "prepulled"
    ASSIGNED = "assigned"
    RUNNING = "running"
    REFUSED = "refused"
    COMPLETED = "completed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    DISCONNECTED = "disconnected"
    DESTROYED = "destroyed"
    PROVEN_CLEAN = "proven_clean"
    QUARANTINED = "quarantined"


TERMINAL_JOB_STATES = frozenset(
    {
        JobState.COMPLETED,
        JobState.TIMED_OUT,
        JobState.CANCELLED,
        JobState.DISCONNECTED,
    }
)

# What each state may move to. An arrow that is not here does not exist, and
# the refusal names the pair rather than shrugging. There is deliberately no
# edge from `DESTROYED` back to `PREPULLED`: an instance whose job ended is
# capacity that has to be proved clean before its slot is filled again.
_TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.PREPULLED: frozenset({JobState.ASSIGNED, JobState.DESTROYED}),
    JobState.ASSIGNED: frozenset(
        {JobState.RUNNING, JobState.REFUSED, JobState.CANCELLED}
    ),
    JobState.RUNNING: frozenset(TERMINAL_JOB_STATES),
    JobState.REFUSED: frozenset({JobState.DESTROYED}),
    JobState.COMPLETED: frozenset({JobState.DESTROYED}),
    JobState.TIMED_OUT: frozenset({JobState.DESTROYED}),
    JobState.CANCELLED: frozenset({JobState.DESTROYED}),
    JobState.DISCONNECTED: frozenset({JobState.DESTROYED}),
    JobState.DESTROYED: frozenset({JobState.PROVEN_CLEAN, JobState.QUARANTINED}),
    JobState.PROVEN_CLEAN: frozenset(),
    JobState.QUARANTINED: frozenset(),
}

# The states in which an instance holds a job, and must therefore name it.
_JOB_NAMED_STATES = frozenset(
    {
        JobState.ASSIGNED,
        JobState.RUNNING,
        JobState.REFUSED,
        JobState.COMPLETED,
        JobState.TIMED_OUT,
        JobState.CANCELLED,
        JobState.DISCONNECTED,
    }
)

_CLEANUP = ErrorKind.CLEANUP_FAILURE


def next_states(state: JobState) -> frozenset[JobState]:
    """The transitions that exist from `state`; an empty set is terminal."""

    if not isinstance(state, JobState):
        raise AdapterError(
            ErrorKind.UNKNOWN_STATE,
            f"lifecycle.next_states: must be a JobState, not "
            f"{type(state).__name__}",
        )
    return _TRANSITIONS[state]


def _refuse_transition(current: JobState, wanted: object) -> AdapterError:
    return AdapterError(
        ErrorKind.UNKNOWN_STATE,
        f"lifecycle: {current.value} has no transition to {_name_of(wanted)}",
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class JobLifecycle:
    """One instance's path from warm stock to proven clean or quarantined.

    The named methods are the vocabulary — offer, start, refuse, finish,
    destroy, prove, quarantine — and each one carries the rule its name
    promises. `move` is the table underneath them, exposed so a caller can be
    told exactly which arrow does not exist.
    """

    instance_id: str
    image_digest: str
    state: JobState = JobState.PREPULLED
    job_id: str | None = None

    def __post_init__(self) -> None:
        _identity(
            self.instance_id, "job_lifecycle.instance_id",
            ErrorKind.INVALID_DESIRED_STATE,
        )
        _digest_checked(
            self.image_digest, "job_lifecycle.image_digest",
            ErrorKind.INVALID_DESIRED_STATE,
        )
        if not isinstance(self.state, JobState):
            raise AdapterError(
                ErrorKind.UNKNOWN_STATE,
                "job_lifecycle.state: must be a JobState, not "
                f"{type(self.state).__name__}",
            )
        if self.state is JobState.PREPULLED and self.job_id is not None:
            raise AdapterError(
                ErrorKind.UNKNOWN_STATE,
                "job_lifecycle.job_id: an instance that has accepted no job "
                "has no job identity",
            )
        if self.state in _JOB_NAMED_STATES and self.job_id is None:
            raise AdapterError(
                ErrorKind.UNKNOWN_STATE,
                f"job_lifecycle.job_id: state {self.state.value} is one the "
                "instance reached by accepting a job — it must name the job",
            )

    def _transition(self, state: JobState, **changes) -> "JobLifecycle":
        """The one place a state change happens, so the table is the authority.

        Every named method below ends here. A state a method could otherwise
        reach by building a new value directly is a state the table does not
        govern, which is how the fourth slice's battery found `offer` bypassing
        the arrow it depended on.
        """

        if not isinstance(state, JobState):
            # A `str` that spells a state is still a string, and a str-Enum
            # compares equal to its own spelling — so this is checked before
            # the table, whose membership test would let `"completed"` through.
            raise _refuse_transition(self.state, state)
        if state not in _TRANSITIONS[self.state]:
            raise _refuse_transition(self.state, state)
        return replace(self, state=state, **changes)

    def move(self, state: JobState) -> "JobLifecycle":
        """The transition table, and nothing else."""

        return self._transition(state)

    def offer(self, job_id: str) -> "JobLifecycle":
        """Accept one job. A second offer is a policy denial.

        `offer` is where RUN-001's "at most one job" is decided, so it is
        checked before the table: an instance in a terminal state has no arrow
        to `ASSIGNED` either, but the reason a caller must be told is that it
        already took one.
        """

        if self.state is not JobState.PREPULLED:
            raise AdapterError(
                ErrorKind.POLICY_DENIAL,
                "lifecycle: one job per instance — "
                f"{self.instance_id} is {self.state.value} and cannot take "
                "another job",
            )
        if not isinstance(job_id, str) or not job_id:
            raise AdapterError(
                ErrorKind.POLICY_DENIAL,
                "lifecycle.offer: job_id must be a non-empty string",
            )
        _identity(job_id, "lifecycle.offer.job_id", ErrorKind.POLICY_DENIAL)
        return self._transition(JobState.ASSIGNED, job_id=job_id)

    def start(self) -> "JobLifecycle":
        """The job is running. Only from `ASSIGNED`."""

        return self.move(JobState.RUNNING)

    def refuse(self) -> "JobLifecycle":
        """The offer is declined before the job starts; the instance is spent."""

        return self.move(JobState.REFUSED)

    def finish(self, outcome: JobState) -> "JobLifecycle":
        """Reach a terminal job state: completed, timed out, cancelled, or an
        uncertain disconnect.

        There is no second check that `outcome` is terminal: the only state
        `finish` can act from is `RUNNING`, whose arrows are exactly the four
        terminal states, so the table already refuses everything else. The
        first battery for this module proved that a copy of the rule there was
        unreachable (M8).
        """

        return self._transition(outcome)

    def destroy(self) -> "JobLifecycle":
        """Every path out of a job ends here — including one that never took one."""

        return self.move(JobState.DESTROYED)

    def prove(self, evidence: CleanupEvidence) -> "JobLifecycle":
        """Clean-by-proof: proven clean only on an admissible proof about *this*
        instance and *this* image.

        Whether the instance has been destroyed is the table's business — only
        a destroyed instance has an arrow to `PROVEN_CLEAN` — and this method
        checks the proof rather than repeating that rule (M22).
        """

        if not isinstance(evidence, CleanupEvidence):
            raise AdapterError(
                _CLEANUP, "lifecycle.prove: must be given CleanupEvidence"
            )
        if not evidence.admissible:
            raise AdapterError(
                _CLEANUP,
                "lifecycle.prove: the proof reports a failed disposal and is "
                "not proof of cleanup",
            )
        if evidence.instance_id != self.instance_id:
            raise AdapterError(
                _CLEANUP,
                "lifecycle.prove: the proof is about another instance — a "
                "proof cannot be transplanted",
            )
        if evidence.image_digest != self.image_digest:
            raise AdapterError(
                _CLEANUP,
                "lifecycle.prove: the proof is about another image — a proof "
                "cannot be transplanted onto a later generation",
            )
        return self.move(JobState.PROVEN_CLEAN)

    def quarantine(self, quarantine: Quarantine) -> "JobLifecycle":
        """RUN-002's other branch: hold the resources, keep the reason."""

        if not isinstance(quarantine, Quarantine):
            raise AdapterError(
                _CLEANUP, "lifecycle.quarantine: must be given a Quarantine"
            )
        if quarantine.instance_id != self.instance_id:
            raise AdapterError(
                _CLEANUP,
                "lifecycle.quarantine: the quarantine names another instance",
            )
        return self.move(JobState.QUARANTINED)


@dataclass(frozen=True, slots=True, kw_only=True)
class AdmissionGate:
    """What must be proved or quarantined before its capacity may be replaced.

    RUN-002's rule is about the *replacement*, not about the destroy: destroy
    is an operation, admission is the decision. So the gate records instances
    that have been destroyed and are neither proven clean nor quarantined —
    the only state in which replacing that capacity is forbidden.
    """

    unaccounted: tuple[str, ...] = ()
    proven: tuple[CleanupEvidence, ...] = ()
    quarantined: tuple[Quarantine, ...] = ()

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for instance_id in self.unaccounted:
            _identity(instance_id, "admission_gate.unaccounted",
                      ErrorKind.POLICY_DENIAL)
            if instance_id in seen:
                raise AdapterError(
                    ErrorKind.POLICY_DENIAL,
                    f"admission_gate.unaccounted: {instance_id} appears twice",
                )
            seen.add(instance_id)
        for evidence in self.proven:
            if not isinstance(evidence, CleanupEvidence):
                raise AdapterError(
                    ErrorKind.POLICY_DENIAL,
                    "admission_gate.proven: must hold CleanupEvidence",
                )
        for quarantine in self.quarantined:
            if not isinstance(quarantine, Quarantine):
                raise AdapterError(
                    ErrorKind.POLICY_DENIAL,
                    "admission_gate.quarantined: must hold Quarantine",
                )

    @property
    def shortfall(self) -> int:
        """How many instances' capacity cannot be replaced yet."""

        return len(self.unaccounted)

    @property
    def can_admit(self) -> bool:
        return not self.unaccounted

    def destroyed(self, instance_id: str) -> "AdmissionGate":
        """The instance is gone and nothing has accounted for it yet."""

        _identity(instance_id, "admission_gate.destroyed.instance_id",
                  ErrorKind.POLICY_DENIAL)
        if instance_id in self.unaccounted:
            raise AdapterError(
                ErrorKind.POLICY_DENIAL,
                f"admission_gate: {instance_id} is already unaccounted for",
            )
        return replace(self, unaccounted=self.unaccounted + (instance_id,))

    def prove(self, evidence: CleanupEvidence) -> "AdmissionGate":
        if not isinstance(evidence, CleanupEvidence):
            raise AdapterError(
                _CLEANUP, "admission_gate.prove: must be given CleanupEvidence"
            )
        if evidence.instance_id not in self.unaccounted:
            raise AdapterError(
                _CLEANUP,
                f"admission_gate.prove: {evidence.instance_id} is not awaiting "
                "an accounting",
            )
        return replace(
            self,
            unaccounted=tuple(
                item for item in self.unaccounted if item != evidence.instance_id
            ),
            proven=self.proven + (evidence,),
        )

    def quarantine(self, quarantine: Quarantine) -> "AdmissionGate":
        if not isinstance(quarantine, Quarantine):
            raise AdapterError(
                _CLEANUP,
                "admission_gate.quarantine: must be given a Quarantine",
            )
        if quarantine.instance_id not in self.unaccounted:
            raise AdapterError(
                _CLEANUP,
                f"admission_gate.quarantine: {quarantine.instance_id} is not "
                "awaiting an accounting",
            )
        return replace(
            self,
            unaccounted=tuple(
                item
                for item in self.unaccounted
                if item != quarantine.instance_id
            ),
            quarantined=self.quarantined + (quarantine,),
        )


def admit_replacement(
    gate: AdmissionGate,
    pool: WarmPool,
    instance: WarmInstance,
    *,
    replacing: str | None = None,
) -> WarmPool:
    """RUN-002 as the one call that admits capacity.

    `replacing` names the instance whose capacity this one replaces. While that
    instance is neither proved clean nor quarantined, the capacity does not
    exist to be replaced. New capacity (no `replacing`) is not held up by
    somebody else's unfinished accounting — RUN-002 constrains the replacement,
    not the pool's growth.
    """

    if not isinstance(gate, AdmissionGate):
        raise AdapterError(
            ErrorKind.POLICY_DENIAL,
            "admit_replacement: must be given an AdmissionGate",
        )
    if replacing is not None:
        _identity(replacing, "admit_replacement.replacing",
                  ErrorKind.POLICY_DENIAL)
        if replacing in gate.unaccounted:
            raise AdapterError(
                ErrorKind.POLICY_DENIAL,
                f"admit_replacement: {replacing} is destroyed and unaccounted "
                "for — its cleanup is neither proven nor quarantined, so its "
                "capacity cannot be replaced",
            )
    # Checked here rather than left to the pool's constructor so the refusal
    # arrives typed: a pool at its ceiling is CAPACITY_EXHAUSTION (Sec. 5.2),
    # and the one place that can say so is the call that admits capacity.
    if pool.warm_count >= pool.pool.warm_max:
        raise AdapterError(
            ErrorKind.CAPACITY_EXHAUSTION,
            f"admit_replacement: pool {pool.pool.pool_id!r} is at "
            f"warm_max {pool.pool.warm_max}",
        )
    try:
        return pool.admit(instance)
    except AdapterContractError as exc:
        raise AdapterError(ErrorKind.INVALID_DESIRED_STATE, str(exc)) from None
