# spec: fleet-002-02, fleet-002-03, fleet-002-04
"""Apply: the one place a plan becomes a new revision (FLEET-002).

Three rules, each enforced rather than documented:

1. **Bound to its revision.** A plan may only apply to the revision it was
   planned against. Anything else is a stale plan, refused with both revisions
   named — never rebased onto the newer state, because a rebase is a plan
   nobody reviewed.
2. **Authorized.** A destructive plan needs `fleet.admin`; every plan needs
   `fleet.apply`. The principal that was authorized is stored on every audit
   event, so the decision and the record cannot name different actors.
3. **Idempotent by key.** Re-sending the same key with the same plan returns
   the recorded result and touches no state. Re-using a key for a different
   plan is refused: a key is a promise about *which* work it covers, and
   quietly widening it is how a retry becomes a second deploy.

Every refusal is a value (`ApplyRefused.audit_log`) as well as an exception, so
an API layer cannot make a refused attempt invisible in the log.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .audit import AuditEvent, AuditLog, Outcome
from .auth import AuthorizationError, Principal, Scope
from .model import DesiredState, ModelError, _instant
from .plan import Plan, simulate

_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ApplyError(ValueError):
    """An apply that did not happen. Never implies a partial apply."""


class ApplyRefused(ApplyError):
    """A refusal before any change was made, carrying the log that records it."""

    def __init__(self, message: str, audit_log: AuditLog) -> None:
        super().__init__(message)
        self.audit_log = audit_log

    @property
    def event(self) -> AuditEvent:
        return self.audit_log.events[-1]


@dataclass(frozen=True, slots=True, kw_only=True)
class IdempotencyLedger:
    """Which key applied which plan, and what revision that produced."""

    entries: tuple[tuple[str, str, int], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.entries, tuple):
            raise ApplyError("idempotency.entries: must be a tuple")
        seen: set[str] = set()
        for index, entry in enumerate(self.entries):
            if not isinstance(entry, tuple) or len(entry) != 3:
                raise ApplyError(
                    f"idempotency.entries[{index}]: must be (key, plan_id, revision)"
                )
            key, plan_id, revision = entry
            _key(key, f"idempotency.entries[{index}].key")
            if not isinstance(plan_id, str) or not plan_id.startswith("plan:"):
                raise ApplyError(
                    f"idempotency.entries[{index}].plan_id: must be a plan id"
                )
            if not isinstance(revision, int) or isinstance(revision, bool) or revision < 2:
                raise ApplyError(
                    f"idempotency.entries[{index}].revision: must be an integer >= 2"
                )
            if key in seen:
                raise ApplyError(
                    f"idempotency.entries[{index}]: key {key} appears twice"
                )
            seen.add(key)

    def lookup(self, idempotency_key: str) -> tuple[str, int] | None:
        for key, plan_id, revision in self.entries:
            if key == idempotency_key:
                return plan_id, revision
        return None

    def with_applied(
        self, *, idempotency_key: str, plan_id: str, resulting_revision: int
    ) -> "IdempotencyLedger":
        _key(idempotency_key, "idempotency.key")
        if self.lookup(idempotency_key) is not None:
            raise ApplyError(
                f"idempotency: key {idempotency_key} is already recorded; "
                "a ledger is appended to, never rewritten"
            )
        return IdempotencyLedger(
            entries=self.entries + ((idempotency_key, plan_id, resulting_revision),)
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ApplyResult:
    state: DesiredState
    audit_log: AuditLog
    ledger: IdempotencyLedger
    plan_id: str
    base_revision: int
    resulting_revision: int
    replayed: bool


def apply_plan(
    *,
    state: DesiredState,
    plan: Plan,
    principal: Principal,
    at: str,
    idempotency_key: str,
    ledger: IdempotencyLedger | None = None,
    audit_log: AuditLog | None = None,
) -> ApplyResult:
    """Apply `plan` to `state` as `principal`, once per `idempotency_key`."""
    if not isinstance(state, DesiredState):
        raise ApplyError(
            f"apply: state must be a DesiredState, not {type(state).__name__}"
        )
    if not isinstance(plan, Plan):
        raise ApplyError(f"apply: plan must be a Plan, not {type(plan).__name__}")
    if not isinstance(principal, Principal):
        raise ApplyError(
            f"apply: principal must be a Principal, not {type(principal).__name__}"
        )
    _key(idempotency_key, "apply.idempotency_key")
    try:
        _instant(at, "apply.at")
    except ModelError as exc:
        raise ApplyError(str(exc)) from None
    log = AuditLog() if audit_log is None else audit_log
    book = IdempotencyLedger() if ledger is None else ledger

    def refused(message: str) -> ApplyRefused:
        return ApplyRefused(
            message,
            log.append(
                at=at,
                actor=principal,
                action="apply",
                subject=plan.plan_id,
                outcome=Outcome.REFUSED,
                plan_id=plan.plan_id,
                idempotency_key=idempotency_key,
                reason=message,
            ),
        )

    # 1. Authorization, before anything else — including a replay.
    try:
        principal.require(Scope.FLEET_APPLY)
        if plan.destructive:
            principal.require(Scope.FLEET_ADMIN)
    except AuthorizationError as exc:
        raise refused(str(exc)) from None

    # 2. Idempotency. Same key and same plan: the work already happened.
    previous = book.lookup(idempotency_key)
    if previous is not None:
        recorded_plan, recorded_revision = previous
        if recorded_plan != plan.plan_id:
            raise refused(
                f"idempotency: key {idempotency_key} was already used for plan "
                f"{recorded_plan}; it cannot also cover {plan.plan_id}"
            )
        return ApplyResult(
            state=state,
            audit_log=log.append(
                at=at,
                actor=principal,
                action="apply",
                subject=plan.plan_id,
                outcome=Outcome.REPLAYED,
                plan_id=plan.plan_id,
                idempotency_key=idempotency_key,
            ),
            ledger=book,
            plan_id=plan.plan_id,
            base_revision=plan.base_revision,
            resulting_revision=recorded_revision,
            replayed=True,
        )

    # 3. The revision the plan was reviewed against.
    if plan.base_revision != state.revision:
        raise refused(
            f"stale plan {plan.plan_id}: planned against revision "
            f"{plan.base_revision}, the state is at revision {state.revision}"
        )

    # 4. Execute. Revalidated against the real state and the real time even
    #    though the plan already simulated it: a plan is a prediction. Entries
    #    are collected on a pending log and only committed once the whole plan
    #    has applied — a plan is one revision, so its record appears as one.
    working = state
    pending = log
    for index, change in enumerate(plan.changes):
        try:
            working = simulate(working, change, at=at)
        except ModelError as exc:
            raise refused(
                f"change {index} ({change.kind.value}) is not possible: {exc}"
            ) from None
        pending = pending.append(
            at=at,
            actor=principal,
            action=change.kind.value,
            subject=change.subject,
            outcome=Outcome.APPLIED,
            plan_id=plan.plan_id,
            idempotency_key=idempotency_key,
        )

    if working.revision != plan.resulting_revision:
        # Not a refusal: the plan was self-consistent when it was built, so this
        # is an implementation fault, and it must not be recorded as success.
        raise ApplyError(
            f"apply: produced revision {working.revision}, the plan declared "
            f"{plan.resulting_revision}"
        )

    book = book.with_applied(
        idempotency_key=idempotency_key,
        plan_id=plan.plan_id,
        resulting_revision=working.revision,
    )
    return ApplyResult(
        state=working,
        audit_log=pending,
        ledger=book,
        plan_id=plan.plan_id,
        base_revision=plan.base_revision,
        resulting_revision=working.revision,
        replayed=False,
    )


def _key(value: object, where: str) -> str:
    if not isinstance(value, str) or not _KEY.match(value):
        raise ApplyError(
            f"{where}: must match [A-Za-z0-9][A-Za-z0-9._:-]{{0,127}}"
        )
    return value
