# spec: fleet-001-01
"""What a host reports — and nothing else (FLEET-001).

An observation is evidence about the world, not a claim on it. This module is
kept apart from `model.py` on purpose: neither imports the other, and there is
no constructor anywhere that turns an `Observation` into desired state. The
test suite reads both files and fails if either one starts importing the other,
because "the agent must not become the database" is a property of the code, not
of a comment.

Comparing observations against desired state (and computing the diff) is the
reconciler's job (Sprint 2 box 2.3); a comparison returns a diff, never a state.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class ObservationError(ValueError):
    """A malformed report. Names the field, never the value."""


def _identifier(value: object, where: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.match(value):
        raise ObservationError(f"{where}: must be a lowercase identifier")
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class ObservedRunner:
    """A runner process a host believes is running."""

    runner_id: str
    pool_id: str
    started_at: str
    job_id: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.runner_id, "observed_runner.runner_id")
        _identifier(self.pool_id, "observed_runner.pool_id")
        if not isinstance(self.started_at, str) or not self.started_at:
            raise ObservationError(
                "observed_runner.started_at: must be a timestamp string"
            )
        if self.job_id is not None and (
            not isinstance(self.job_id, str) or not self.job_id
        ):
            raise ObservationError("observed_runner.job_id: must be a non-empty string")


@dataclass(frozen=True, slots=True, kw_only=True)
class Observation:
    """One host's report at one moment. Immutable, and never authoritative."""

    host_id: str
    observed_at: str
    runners: tuple[ObservedRunner, ...] = ()
    agent_version: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.host_id, "observation.host_id")
        if not isinstance(self.observed_at, str) or not self.observed_at:
            raise ObservationError("observation.observed_at: must be a timestamp string")
        if not isinstance(self.runners, tuple):
            raise ObservationError("observation.runners: must be a tuple")
        for index, runner in enumerate(self.runners):
            if not isinstance(runner, ObservedRunner):
                raise ObservationError(
                    f"observation.runners[{index}]: must be an ObservedRunner"
                )
        if self.agent_version is not None and (
            not isinstance(self.agent_version, str) or not self.agent_version
        ):
            raise ObservationError("observation.agent_version: must be a non-empty string")

    @property
    def runner_count(self) -> int:
        return len(self.runners)
