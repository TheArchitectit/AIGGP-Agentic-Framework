# // spec: coh-ctx-01, coh-ctx-02, coh-ctx-03
"""Evaluation-context loading and validation. Time and stage come only from
this control-plane-issued manifest, never from the host clock or request.
Distinguishes fresh-promotion from replay semantics.
"""
import json
from pathlib import Path

from . import canon


class ContextError(ValueError):
    """Untrusted or invalid context (exit-31 class)."""


VALID_STAGES = {0, 1, 2, 3, 4}
VALID_SEMANTICS = {"fresh-promotion", "replay"}


def load(root: str) -> dict:
    """Load and validate an evaluation context from `root`/context.json."""
    fp = Path(root).resolve() / "context.json"
    if not fp.exists():
        raise ContextError(f"missing evaluation context: {fp}")
    try:
        ctx = json.loads(fp.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise ContextError(f"cannot read context {fp}: {e}") from e

    if ctx.get("api_version") != "devgate.spec-coherence.context/v1":
        raise ContextError(
            f"unsupported context api_version: {ctx.get('api_version')!r}")

    # Shape-validate against the frozen context contract, so a garbage
    # evaluation_time can never reach adoption._parse (round-4 carry-forward:
    # unparseable timestamps were a caller-reachable exit-1 crash family).
    from . import schemacheck
    try:
        errors = schemacheck.validate(ctx, schemacheck.load("evaluation-context.schema.json"))
    except (OSError, json.JSONDecodeError, schemacheck.SchemaError) as e:
        raise ContextError(f"context schema unavailable: {e}") from e
    if errors:
        raise ContextError("invalid context: " + "; ".join(errors[:5]))

    stage = ctx.get("stage")
    if stage not in VALID_STAGES:
        raise ContextError(f"invalid stage: {stage!r}")

    semantics = ctx.get("semantics", "fresh-promotion")
    if semantics not in VALID_SEMANTICS:
        raise ContextError(f"invalid semantics: {semantics!r}")

    # Trusted issuance: a countersignature or an issuer recorded in the
    # control-plane trust root must be present. A bare self-issued context
    # with no authority fails policy resolution (exit 31).
    issuance = ctx.get("issuance") or {}
    if not issuance.get("issuer"):
        raise ContextError("context has no trusted issuer")

    ctx["context_digest"] = canon.digest_obj("context/v1", ctx)
    return ctx


def is_promotion_authorizing(ctx: dict) -> bool:
    """Only fresh-promotion semantics under a trusted context may authorize."""
    return ctx.get("semantics", "fresh-promotion") == "fresh-promotion"
