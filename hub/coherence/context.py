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

# S6 Cycle A (design.md, round-14): the five adoption modes ARE the five
# stages — one ordinal axis, names derived from the authoritative stage
# record, never a parallel knob (coh-ctx-02). Nothing in the pipeline may
# read a name for behavior; callers use mode_for_stage for display.
_MODES = {0: "inventory", 1: "advisory", 2: "ratchet",
          3: "enforced-core", 4: "enforced-full"}


def mode_for_stage(stage):
    """The derived mode label for an authoritative stage, or None when the
    stage carries no authority (invalid stages get no name, ever)."""
    return _MODES.get(stage) if stage in VALID_STAGES else None


def load(root: str) -> dict:
    """Load and validate an evaluation context from `root`/context.json."""
    fp = Path(root).resolve() / "context.json"
    if not fp.exists():
        raise ContextError(f"missing evaluation context: {fp}")
    try:
        ctx = json.loads(fp.read_text(encoding="utf-8"))
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

    # Trusted issuance (slice scope): an issuer identity is always required.
    # When a control-plane key IS configured, the HMAC countersignature is
    # mandatory too — an unsigned context must not pass where a verifier
    # exists (the S5 signing milestone tightens this to signer-set
    # verification, coh-ev-05).
    issuance = ctx.get("issuance") or {}
    if not issuance.get("issuer"):
        raise ContextError("context has no trusted issuer")
    from . import issue
    if issue._key() is not None and not issue.verify_signature(ctx):
        raise ContextError("control-plane key configured but context is "
                           "unsigned or the countersignature does not verify")

    ctx["context_digest"] = canon.digest_obj("context/v1", ctx)
    return ctx


def load_captured_facts(root: str, ctx: dict) -> dict:
    """Digest-verified content for the context's captured facts (coh-rt-03,
    coh-ctx-04). Each bound record carries (fact_id, digest); the captured
    response content lives at <root>/facts/<fact_id>.json and is verified
    against the bound digest — replay consumes the captured content, never a
    live fetch (default-deny: no network path exists in the service). A
    record with a null digest binds no content and is omitted here; the
    runner resolves any assertion depending on it as UNRESOLVED.
    """
    base = Path(root).resolve()
    out = {}
    for rec in ctx.get("captured_facts") or []:
        if not isinstance(rec, dict) or not rec.get("fact_id"):
            raise ContextError("captured fact record missing fact_id")
        fid = rec["fact_id"]
        if "/" in fid or fid in (".", ".."):
            raise ContextError(f"captured-fact-bad-id:{fid}")
        dig = rec.get("digest")
        if not dig:
            continue
        fp = base / "facts" / fid
        try:
            raw = fp.read_bytes()
        except OSError:
            raise ContextError(f"captured-fact-content-missing:{fid}") from None
        if canon.digest_bytes("file/v1", raw) != dig:
            raise ContextError(f"captured-fact-tampered:{fid}")
        try:
            out[fid] = json.loads(raw)
        except json.JSONDecodeError:
            raise ContextError(f"captured-fact-unparseable:{fid}") from None
    return out


def verify_bound_sets(ctx: dict, baseline: list, exceptions: list) -> None:
    """Cross-check bound set digests (coh-ctx-01): when the context names a
    baseline/exception digest, the sets actually loaded from the policy must
    hash to it — a policy swapped after issuance is detected here."""
    for digest_key, entries, label in (
            ("baseline_set_digest", baseline, "baseline"),
            ("exception_set_digest", exceptions, "exception")):
        claimed = ctx.get(digest_key)
        if claimed:
            from . import issue
            actual = issue.set_digest(entries, label)
            if actual != claimed:
                raise ContextError(
                    f"{label} set does not match the digest bound in the "
                    f"context ({claimed}); sets must be written to the policy "
                    f"directory at issuance")


def is_promotion_authorizing(ctx: dict) -> bool:
    """Only fresh-promotion semantics under a trusted context may authorize."""
    return ctx.get("semantics", "fresh-promotion") == "fresh-promotion"
