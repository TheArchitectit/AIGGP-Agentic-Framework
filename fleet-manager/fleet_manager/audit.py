# spec: fleet-002-03
"""The audit log: append-only, contiguous, and unable to run backwards.

An audit log is only evidence if it cannot be edited after the fact, and only
useful if a missing entry is detectable. Both are enforced structurally here:

- `AuditLog` is frozen; `append()` returns a new log and never edits one;
- sequence numbers must be exactly 1..n with no gap and no reordering;
- timestamps must not go backwards, so an entry cannot be back-dated into a
  log that already covers that instant.

The actor on an event is the `auth.Principal` the authorization decision was
made against — the same object — so the log and the decision cannot disagree
about who acted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .auth import Principal
from .model import ModelError, _instant

_ACTION = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")

# A reason string that looks like it embeds a credential is refused rather than
# stored: the same rule as the document layer, applied to the log. The patterns
# match shapes, and the refusal never repeats the value.
_SECRET_SHAPED = re.compile(
    r"(?i)(gh[pousr]_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)


class AuditError(ValueError):
    """A log that is not a log. Names the entry and the broken rule."""


class Outcome(str, Enum):
    APPLIED = "applied"
    REFUSED = "refused"
    REPLAYED = "replayed"


@dataclass(frozen=True, slots=True, kw_only=True)
class AuditEvent:
    seq: int
    at: str
    actor: Principal
    action: str
    subject: str
    outcome: Outcome
    plan_id: str | None = None
    idempotency_key: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.seq, int) or isinstance(self.seq, bool) or self.seq < 1:
            raise AuditError("audit_event.seq: must be an integer >= 1")
        _event_instant(self.at, "audit_event.at")
        if not isinstance(self.actor, Principal):
            raise AuditError("audit_event.actor: must be a Principal")
        if not isinstance(self.action, str) or not _ACTION.match(self.action):
            raise AuditError(
                "audit_event.action: must be a lowercase token (a-z 0-9 . _ -, 1-64 chars)"
            )
        if not isinstance(self.subject, str) or not self.subject:
            raise AuditError("audit_event.subject: must be a non-empty string")
        if not isinstance(self.outcome, Outcome):
            options = ", ".join(outcome.value for outcome in Outcome)
            raise AuditError(f"audit_event.outcome: must be one of {options}")
        if self.plan_id is not None and not isinstance(self.plan_id, str):
            raise AuditError("audit_event.plan_id: must be a string or None")
        if self.idempotency_key is not None and not isinstance(
            self.idempotency_key, str
        ):
            raise AuditError("audit_event.idempotency_key: must be a string or None")
        if self.reason is not None:
            if not isinstance(self.reason, str) or not self.reason:
                raise AuditError(
                    "audit_event.reason: must be a non-empty string or None"
                )
            if _SECRET_SHAPED.search(self.reason):
                raise AuditError(
                    "audit_event.reason: looks like it carries a secret value; "
                    "record the refusal, not the value"
                )

    def document(self) -> dict:
        return {
            "seq": self.seq,
            "at": self.at,
            "actor": {"kind": self.actor.kind.value, "id": self.actor.principal_id},
            "action": self.action,
            "subject": self.subject,
            "outcome": self.outcome.value,
            "plan_id": self.plan_id,
            "idempotency_key": self.idempotency_key,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class AuditLog:
    events: tuple[AuditEvent, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.events, tuple):
            raise AuditError("audit_log.events: must be a tuple of AuditEvent")
        for index, event in enumerate(self.events):
            if not isinstance(event, AuditEvent):
                raise AuditError(
                    f"audit_log.events[{index}]: must be an AuditEvent, "
                    f"not {type(event).__name__}"
                )
            if event.seq != index + 1:
                raise AuditError(
                    f"audit_log.events[{index}]: seq {event.seq} breaks the "
                    f"contiguous 1..n sequence (expected {index + 1})"
                )
            if index:
                previous = self.events[index - 1]
                if _event_instant(event.at, "audit_event.at") < _event_instant(
                    previous.at, "audit_event.at"
                ):
                    raise AuditError(
                        f"audit_log.events[{index}]: timestamp precedes the "
                        f"previous entry — an audit log does not run backwards"
                    )

    @property
    def head_seq(self) -> int:
        return len(self.events)

    def append(
        self,
        *,
        at: str,
        actor: Principal,
        action: str,
        subject: str,
        outcome: Outcome,
        plan_id: str | None = None,
        idempotency_key: str | None = None,
        reason: str | None = None,
    ) -> AuditLog:
        return AuditLog(
            events=self.events
            + (
                AuditEvent(
                    seq=self.head_seq + 1,
                    at=at,
                    actor=actor,
                    action=action,
                    subject=subject,
                    outcome=outcome,
                    plan_id=plan_id,
                    idempotency_key=idempotency_key,
                    reason=reason,
                ),
            )
        )

    def for_plan(self, plan_id: str) -> tuple[AuditEvent, ...]:
        return tuple(event for event in self.events if event.plan_id == plan_id)

    def after(self, seq: int) -> tuple[AuditEvent, ...]:
        return tuple(event for event in self.events if event.seq > seq)


def _event_instant(value: str, where: str):
    try:
        return _instant(value, where)
    except ModelError as exc:
        raise AuditError(str(exc)) from None
