# spec: fleet-007-01, fleet-007-02, fleet-007-03, fleet-007-04
"""The stable adapter contract, the pinned image, and what "warm" means.

Sprint 3 established who is calling (FLEET-004), what a call may ask for
(FLEET-005), and what the manager tells a host to become (FLEET-006). Nothing
in the package can yet *act* on a host. This module is the shape the thing that
acts must have, and it is deliberately the shape only: no Docker, no Podman, no
process. Two properties of that shape are worth stating before the code:

1. **The contract is checked without being called.** `check_contract()` reads
   signatures. A conformance test that calls eleven happy paths proves an
   implementation works today and says nothing about the call nobody wrote a
   test for; a signature check states what the implementation promises, and a
   fake whose methods raise on call still conforms — which the suite proves,
   because that is the difference between the two kinds of check.
2. **Warmth is a state, not a count.** The program's RUN-001 permits a warm pool
   to keep "pre-pulled images or stopped clean containers" and forbids keeping
   "a previously used job filesystem". `USED` is therefore a state an instance
   can be in, not an absence: an instance that has run a job still exists, still
   holds its name, and is exactly the one that must never be handed to the next
   job.

The image decision comes from the repository's own runner standard
(`templates/runner/`): the official `ghcr.io/actions/actions-runner`, pinned by
digest, with no hand-rolled fork and no forked entrypoint. `STANDARD_RUNNER_IMAGE_DIGEST`
is that digest, and a test binds it to the quadlet that records it, so the
package cannot pin an image the fleet does not run.

Two parameter names carry rules rather than data and are part of the contract:
`registration_ref` (a reference, never the material — SEC-001, as in
`operations`) and `operation_key` on every mutating call (Sec. 5.2: "idempotent
or carry a durable operation key"). A `**kwargs` does not satisfy either name: a
catch-all accepts a call it does not implement.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from enum import Enum

from .audit import _SECRET_SHAPED
from .model import ModelError, Pool, Runtime, _identifier

# Sec. 5.2's list, in the order the program gives it. One contract, one order:
# a conformance report that reorders the calls is a report nobody can diff.
ADAPTER_CALLS = (
    "discover_capabilities",
    "validate_host",
    "ensure_image",
    "create_runner",
    "observe_runner",
    "mark_drain",
    "cancel_or_timeout",
    "destroy_runner",
    "prove_cleanup",
    "report_receipts",
    "rollback_configuration",
)

# Calls that change something on the host. Each one must be idempotent or carry
# a durable operation key (Sec. 5.2), so each one takes `operation_key`.
MUTATING_CALLS = frozenset({
    "ensure_image",
    "create_runner",
    "mark_drain",
    "cancel_or_timeout",
    "destroy_runner",
    "rollback_configuration",
})

# The parameter that carries a rule, per call, beyond `operation_key`.
REQUIRED_PARAMETERS = {
    "ensure_image": "digest",
    "create_runner": "registration_ref",
    "cancel_or_timeout": "policy",
    "prove_cleanup": "instance_id",
}

# A parameter with one of these names would mean the adapter expects the
# registration *material* rather than a reference to it. The refusal is by name
# so it fires before anything is passed.
_MATERIAL_SHAPED = frozenset({
    "credential", "credentials", "password", "registration_token", "secret",
    "token",
})

RUNNER_IMAGE_REPOSITORY = "ghcr.io/actions/actions-runner"

# The digest the runner standard validated and records in
# `templates/runner/self-hosted-runner.container`. Bound to that file by a
# skip-guarded test rather than trusted as a comment.
STANDARD_RUNNER_IMAGE_DIGEST = (
    "sha256:e5496277be5d09bc968b3d64911b74e219ac4a3f2edce956a3ecf9271bea1ef4"
)

_MAX_DETAIL = 512


class AdapterContractError(ValueError):
    """An adapter, pool, or instance was refused. Names the rule, never a value."""


class ErrorKind(str, Enum):
    """Sec. 5.2's typed errors, exactly. An adapter may not invent a ninth."""

    INVALID_DESIRED_STATE = "invalid_desired_state"
    UNAVAILABLE_HOST = "unavailable_host"
    REGISTRATION_FAILURE = "registration_failure"
    RUNTIME_FAILURE = "runtime_failure"
    CLEANUP_FAILURE = "cleanup_failure"
    CAPACITY_EXHAUSTION = "capacity_exhaustion"
    POLICY_DENIAL = "policy_denial"
    UNKNOWN_STATE = "unknown_state"


class AdapterError(Exception):
    """A typed adapter failure. The kind is an `ErrorKind`, never its spelling.

    `detail` is dropped rather than recorded when it matches the credential
    shape this package already refuses in audit reasons and receipt details:
    the failure of an authenticated call is exactly where the credential ends up
    in a message, and a diagnostic must not become the leak.
    """

    def __init__(self, kind: ErrorKind, detail: str = "") -> None:
        if not isinstance(kind, ErrorKind):
            raise AdapterContractError(
                "adapter_error.kind: must be an ErrorKind ("
                + ", ".join(k.value for k in ErrorKind)
                + "); a string that spells one is still a string"
            )
        if not isinstance(detail, str):
            raise AdapterContractError("adapter_error.detail: must be a string")
        if len(detail) > _MAX_DETAIL:
            raise AdapterContractError(
                f"adapter_error.detail: at most {_MAX_DETAIL} characters"
            )
        if detail and _SECRET_SHAPED.search(detail):
            raise AdapterContractError(
                "adapter_error.detail: looks like it carries a credential; the "
                "value is withheld, not echoed"
            )
        self.kind = kind
        self.detail = detail
        text = f"{kind.value}" + (f": {detail}" if detail else "")
        super().__init__(text)

    def __repr__(self) -> str:  # pragma: no cover - exercised by one assertion
        return f"AdapterError(kind={self.kind.value!r}, detail={self.detail!r})"


def classify(exc: Exception) -> AdapterError:
    """An unexpected exception as a runtime failure, by type and not by message.

    An arbitrary exception's message is uncontrolled text from a CLI, a
    library, or a shell; recording it is how a token that was passed on a
    command line ends up in a log. The type is the part that is safe to keep.
    """

    if isinstance(exc, AdapterError):
        return exc
    return AdapterError(ErrorKind.RUNTIME_FAILURE, type(exc).__name__)


@dataclass(frozen=True)
class AdapterContract:
    """What a candidate adapter satisfied. The runtime is the pool's, not a guess."""

    runtime: Runtime
    calls: tuple[str, ...] = ADAPTER_CALLS

    def __post_init__(self) -> None:
        if not isinstance(self.runtime, Runtime):
            raise AdapterContractError(
                "adapter_contract.runtime: must be a Runtime, not "
                f"{type(self.runtime).__name__}"
            )
        if tuple(self.calls) != ADAPTER_CALLS:
            raise AdapterContractError(
                "adapter_contract.calls: must be exactly the eleven Sec. 5.2 "
                "calls, in order"
            )


def _parameters_of(member) -> dict[str, inspect.Parameter]:
    try:
        return dict(inspect.signature(member).parameters)
    except (TypeError, ValueError) as exc:  # builtins, C callables, partials
        raise AdapterContractError(
            f"adapter: signature cannot be inspected ({type(exc).__name__})"
        ) from None


def check_contract(candidate, *, runtime: Runtime) -> AdapterContract:
    """Check a candidate against Sec. 5.2 without calling anything it defines.

    Every problem found is reported in one refusal. A fresh adapter is usually
    missing several members, and a checker that stops at the first turns one
    review into six.
    """

    if not isinstance(runtime, Runtime):
        raise AdapterContractError(
            f"adapter.runtime: must be a Runtime, not {type(runtime).__name__}"
        )
    if candidate is None:
        raise AdapterContractError("adapter: must be an object, not None")

    # An adapter serves exactly one runtime, and it says which one as a value
    # rather than as the result of a call — a call would be a guess performed
    # by the checker, and a podman adapter handed a docker pool is a wiring
    # error that should fail before a container exists.
    declared = getattr(candidate, "runtime", None)
    if not isinstance(declared, Runtime):
        raise AdapterContractError(
            "adapter.runtime: must be a Runtime declared on the adapter, not "
            f"{type(declared).__name__}"
        )
    if declared is not runtime:
        raise AdapterContractError(
            f"adapter: serves {declared.value!r} but the pool requires "
            f"{runtime.value!r}"
        )

    missing: list[str] = []
    not_callable: list[str] = []
    wrong_signature: list[str] = []

    for name in ADAPTER_CALLS:
        member = getattr(candidate, name, None)
        if member is None:
            missing.append(name)
            continue
        if not callable(member):
            not_callable.append(f"{name} ({type(member).__name__})")
            continue

        parameters = _parameters_of(member)
        required = []
        if name in MUTATING_CALLS:
            required.append("operation_key")
        if name in REQUIRED_PARAMETERS:
            required.append(REQUIRED_PARAMETERS[name])
        for wanted in required:
            if wanted not in parameters:
                wrong_signature.append(f"{name}: no parameter named {wanted!r}")

        if name == "create_runner":
            for suspicious in sorted(set(parameters) & _MATERIAL_SHAPED):
                wrong_signature.append(
                    f"create_runner: parameter {suspicious!r} asks for "
                    "registration material; the contract carries "
                    "registration_ref"
                )

    if missing or not_callable or wrong_signature:
        problems = []
        if missing:
            problems.append("missing: " + ", ".join(missing))
        if not_callable:
            problems.append("not callable: " + ", ".join(not_callable))
        if wrong_signature:
            problems.append("; ".join(wrong_signature))
        raise AdapterContractError(
            f"adapter: does not satisfy the {runtime.value} contract — "
            + " | ".join(problems)
        )

    return AdapterContract(runtime=runtime)


def _identifier_checked(value: str, field: str) -> None:
    """The model's identifier rule, reported as this module's refusal type."""

    try:
        _identifier(value, field)
    except ModelError as exc:
        raise AdapterContractError(str(exc)) from None


def _digest(value: str, field: str) -> None:
    """One definition of a digest inside this module, used by every value.

    The three refusals are distinct because the mistakes are: a tag is a mutable
    name, a reference already carries a repository, and anything else is not a
    digest at all.
    """

    if not isinstance(value, str) or not value:
        raise AdapterContractError(f"{field}: must be sha256:<64 lowercase hex>")
    if "@" in value:
        raise AdapterContractError(
            f"{field}: must be the bare digest, not a reference — the repository "
            "is added by image_reference()"
        )
    if not value.startswith("sha256:"):
        # Anything that is not a digest and not a reference is a name: a tag
        # (`:2.337.0`, `latest`) or a word that means nothing at all. Both are
        # refused as names, because a name is the thing an attacker re-points.
        raise AdapterContractError(
            f"{field}: {value!r} is a tag, and a tag is mutable — it cannot pin "
            "an image; use sha256:<64 lowercase hex>"
        )
    if len(value) != len("sha256:") + 64:
        raise AdapterContractError(f"{field}: must be sha256:<64 lowercase hex>")
    if any(character not in "0123456789abcdef" for character in value[len("sha256:"):]):
        raise AdapterContractError(f"{field}: must be sha256:<64 lowercase hex>")


def image_reference(digest: str) -> str:
    """The runnable reference for one pinned digest.

    A tag is refused: `ghcr.io/actions/actions-runner:2.337.0` is a mutable name
    for an immutable artifact, and the pin exists so that what ran today runs
    again.
    """

    _digest(digest, "image.digest")
    return f"{RUNNER_IMAGE_REPOSITORY}@{digest}"


class InstanceState(str, Enum):
    """What a container is doing. Warmth is two of these, and only two."""

    PREPULLED = "prepulled"
    STOPPED_CLEAN = "stopped_clean"
    RUNNING = "running"
    USED = "used"
    QUARANTINED = "quarantined"


WARM_STATES = frozenset({InstanceState.PREPULLED, InstanceState.STOPPED_CLEAN})


@dataclass(frozen=True)
class WarmInstance:
    """One piece of warm stock, tied to the pool and image it belongs to."""

    instance_id: str
    pool_id: str
    image_digest: str
    state: InstanceState

    def __post_init__(self) -> None:
        _identifier_checked(self.instance_id, "warm_instance.instance_id")
        _identifier_checked(self.pool_id, "warm_instance.pool_id")
        _digest(self.image_digest, "warm_instance.image_digest")
        if not isinstance(self.state, InstanceState):
            raise AdapterContractError(
                "warm_instance.state: must be an InstanceState, not "
                f"{type(self.state).__name__}"
            )

    @property
    def is_warm(self) -> bool:
        return self.state in WARM_STATES


@dataclass(frozen=True)
class WarmPool:
    """The warm stock of one pool, checked against that pool's own contract.

    Every instance is bound to the pool id and to the pool's pinned digest, so a
    container from a previous image generation cannot be counted against the
    current one — the digest is what makes "the same image" mean something.
    """

    pool: Pool
    instances: tuple[WarmInstance, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.pool, Pool):
            raise AdapterContractError("warm_pool.pool: must be a Pool")
        if not isinstance(self.instances, tuple):
            raise AdapterContractError("warm_pool.instances: must be a tuple")

        seen: set[str] = set()
        for instance in self.instances:
            if not isinstance(instance, WarmInstance):
                raise AdapterContractError(
                    "warm_pool.instances: every entry must be a WarmInstance"
                )
            if instance.instance_id in seen:
                raise AdapterContractError(
                    f"warm_pool.instances: duplicate instance id "
                    f"{instance.instance_id!r}"
                )
            seen.add(instance.instance_id)
            if instance.pool_id != self.pool.pool_id:
                raise AdapterContractError(
                    f"warm_pool.instances[{instance.instance_id}]: belongs to pool "
                    f"{instance.pool_id!r}, not {self.pool.pool_id!r}"
                )
            if instance.image_digest != self.pool.image_digest:
                raise AdapterContractError(
                    f"warm_pool.instances[{instance.instance_id}]: image "
                    f"{instance.image_digest} is not this pool's pinned "
                    f"{self.pool.image_digest}"
                )
            if not instance.is_warm:
                raise AdapterContractError(
                    f"warm_pool.instances[{instance.instance_id}]: state "
                    f"{instance.state.value!r} is not warm stock — a container "
                    "that has run a job is never handed to the next one "
                    "(RUN-001)"
                )

        if len(self.instances) > self.pool.warm_max:
            raise AdapterContractError(
                f"warm_pool: {len(self.instances)} instance(s) exceeds "
                f"warm_max {self.pool.warm_max} of pool {self.pool.pool_id!r} "
                "(capacity exhaustion)"
            )

    @property
    def warm_count(self) -> int:
        return len(self.instances)

    @property
    def shortfall(self) -> int:
        return max(0, self.pool.warm_min - self.warm_count)

    @property
    def at_floor(self) -> bool:
        return self.shortfall == 0

    def admit(self, instance: WarmInstance) -> "WarmPool":
        """A new warm pool with one more instance.

        The ceiling is enforced by the constructor and only there: a copy of it
        here would be a second statement of one rule, and the first mutation
        battery for this module removed this copy without a single test
        noticing (M25). A pool at its ceiling refuses the new stock as capacity
        exhaustion, from the one place that defines it.
        """

        if not isinstance(instance, WarmInstance):
            raise AdapterContractError("warm_pool.admit: must be a WarmInstance")
        return WarmPool(pool=self.pool, instances=self.instances + (instance,))

    def retire(self, instance_id: str) -> "WarmPool":
        """A new warm pool without one instance; an unknown id is a refusal."""

        kept = tuple(
            instance for instance in self.instances if instance.instance_id != instance_id
        )
        if len(kept) == len(self.instances):
            raise AdapterContractError(
                f"warm_pool.retire: no instance {instance_id!r} in pool "
                f"{self.pool.pool_id!r}"
            )
        return WarmPool(pool=self.pool, instances=kept)


@dataclass(frozen=True)
class EphemeralInstance:
    """One job's container, defined by what it does not have.

    The standard's persistent runner keeps a durable `/_work` volume so a
    restart reuses the registration. A job instance must have the opposite
    property: an anonymous work directory that goes away with the container.
    `work_dir` is therefore always `None`, and the rendered command carries no
    volume flag at all.

    The registration reference reaches the runner through an environment *file*
    named by `--env-file`, never as `-e RUNNER_TOKEN=<value>`: a value in argv is
    visible in `ps` and in shell history, which is the leak the runner
    standard's own walkthrough avoids.
    """

    instance_id: str
    pool_id: str
    image_digest: str
    registration_env_file: str
    runtime: Runtime
    remove_on_exit: bool = True
    work_dir: None = None

    def __post_init__(self) -> None:
        _identifier_checked(self.instance_id, "ephemeral_instance.instance_id")
        _identifier_checked(self.pool_id, "ephemeral_instance.pool_id")
        _digest(self.image_digest, "ephemeral_instance.image_digest")
        if not isinstance(self.runtime, Runtime):
            raise AdapterContractError(
                "ephemeral_instance.runtime: must be a Runtime, not "
                f"{type(self.runtime).__name__}"
            )
        if self.remove_on_exit is not True:
            raise AdapterContractError(
                "ephemeral_instance.remove_on_exit: must be true — a job "
                "container that outlives its job is the used filesystem "
                "RUN-001 forbids"
            )
        if self.work_dir is not None:
            raise AdapterContractError(
                "ephemeral_instance.work_dir: must be None (anonymous); a named "
                "work directory is a job filesystem that survives the job"
            )
        path = self.registration_env_file
        if not isinstance(path, str) or not path:
            raise AdapterContractError(
                "ephemeral_instance.registration_env_file: must be a non-empty "
                "path to a file the host owns"
            )
        if any(character in path for character in ("\n", "\r", "\0", "=")):
            raise AdapterContractError(
                "ephemeral_instance.registration_env_file: must be a path, not "
                "an environment assignment"
            )
        if _SECRET_SHAPED.search(path):
            raise AdapterContractError(
                "ephemeral_instance.registration_env_file: looks like it carries "
                "a credential; the value is withheld, not echoed"
            )

    def image(self) -> str:
        return image_reference(self.image_digest)

    def command(self) -> tuple[str, ...]:
        """The argument list as a value. Nothing in this module runs it."""

        return (
            self.runtime.value,
            "run",
            "--rm" if self.remove_on_exit else "--detach",
            "--name",
            self.instance_id,
            "--label",
            f"devgate.pool={self.pool_id}",
            "--env",
            "EPHEMERAL=true",
            "--env-file",
            self.registration_env_file,
            self.image(),
        )
