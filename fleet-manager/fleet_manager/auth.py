# spec: fleet-002-02
"""Who may plan and apply. A skeleton, and deliberately nothing more.

This is the authorization *decision*, not the transport: there is no HTTP
handler, no session, no token parsing, and no storage of principals. What it
gives the API layer (Sprint 7) is one place where a request becomes a decision
that can be tested, and one rule that cannot be re-derived differently in a
handler: a destructive apply needs `fleet.admin`, and the principal that was
authorized is the principal the audit log names.

Scopes form a strict ladder — read < plan < apply < admin — and a higher scope
satisfies every lower one. The ladder is explicit in `_SATISFIED_BY` rather
than implied by string comparison, so widening it is a visible diff.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .model import ModelError, _request_id


class AuthorizationError(PermissionError):
    """A principal may not do this. Names the scope, never the principal's data."""


class Scope(str, Enum):
    FLEET_READ = "fleet.read"
    FLEET_PLAN = "fleet.plan"
    FLEET_APPLY = "fleet.apply"
    FLEET_ADMIN = "fleet.admin"


class PrincipalKind(str, Enum):
    OPERATOR = "operator"
    SYSTEM = "system"
    SERVICE = "service"


# scope -> the scopes that satisfy it. A ladder, written out.
_SATISFIED_BY = {
    Scope.FLEET_READ: frozenset(
        {Scope.FLEET_READ, Scope.FLEET_PLAN, Scope.FLEET_APPLY, Scope.FLEET_ADMIN}
    ),
    Scope.FLEET_PLAN: frozenset(
        {Scope.FLEET_PLAN, Scope.FLEET_APPLY, Scope.FLEET_ADMIN}
    ),
    Scope.FLEET_APPLY: frozenset({Scope.FLEET_APPLY, Scope.FLEET_ADMIN}),
    Scope.FLEET_ADMIN: frozenset({Scope.FLEET_ADMIN}),
}


@dataclass(frozen=True, slots=True, kw_only=True)
class Principal:
    """An authenticated actor. Authentication happens elsewhere; this is the result."""

    principal_id: str
    kind: PrincipalKind
    scopes: frozenset[Scope] = frozenset()

    def __post_init__(self) -> None:
        try:
            _request_id(self.principal_id, "principal.principal_id")
        except ModelError as exc:
            raise AuthorizationError(str(exc)) from None
        if not isinstance(self.kind, PrincipalKind):
            options = ", ".join(kind.value for kind in PrincipalKind)
            raise AuthorizationError(f"principal.kind: must be one of {options}")
        if not isinstance(self.scopes, frozenset):
            raise AuthorizationError(
                "principal.scopes: must be a frozenset of Scope (not a string, not a list)"
            )
        for scope in self.scopes:
            if not isinstance(scope, Scope):
                raise AuthorizationError(
                    f"principal.scopes: {scope!r} is not a Scope"
                )

    def holds(self, scope: Scope) -> bool:
        return any(
            granted in _SATISFIED_BY[scope] for granted in self.scopes
        )

    def require(self, scope: Scope) -> None:
        if scope not in _SATISFIED_BY:
            raise AuthorizationError(f"scope: {scope!r} is not a known scope")
        if not self.holds(scope):
            raise AuthorizationError(
                f"authorization refused: {scope.value} is required "
                f"(principal {self.principal_id} holds "
                f"{', '.join(sorted(s.value for s in self.scopes)) or 'no scopes'})"
            )
