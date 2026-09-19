# // spec: coh-ctx-01, coh-ctx-02, coh-pol-05
"""Control-plane stand-in for pilots: issue evaluation contexts, maintain the
stage registry, and build schema-validated baseline/exception sets.

HONEST SCOPE: countersignatures here are HMAC keyed by HUB_COHERENCE_CP_KEY
(hex) — a stand-in until S5 lands detached attestation signing with real key
management (ADR-018). Stage assignment always comes from the registry; a
weaker requested stage is refused, never silently honored (coh-ctx-02).
Sets are written into the POLICY directory (where the CLI reads them) and
their digests are bound into the context (coh-ctx-01; the CLI cross-checks
them at adoption load).
"""
import hashlib
import hmac
import json
import os
from pathlib import Path

from . import attest, canon, schemacheck

CP_KEY_ENV = "HUB_COHERENCE_CP_KEY"
CP_IDENTITY_ENV = "HUB_COHERENCE_CP_IDENTITY"

SIGNATURE_PREFIX = "hmac-sha256:"


def _key():
    raw = os.environ.get(CP_KEY_ENV, "").strip()
    if not raw:
        return None
    try:
        return bytes.fromhex(raw)
    except ValueError:
        raise ValueError(f"{CP_KEY_ENV} must be a hex string") from None


def _unsigned(ctx: dict) -> dict:
    """Deep-copy-safe view of a context without its own countersignature."""
    body = dict(ctx)
    body["issuance"] = {k: v for k, v in (ctx.get("issuance") or {}).items()
                        if k != "countersignature"}
    return body


def sign_context(ctx: dict) -> str:
    key = _key()
    if key is None:
        raise ValueError(f"{CP_KEY_ENV} not configured; cannot sign")
    mac = hmac.new(key, canon.canon(_unsigned(ctx)), hashlib.sha256)
    return SIGNATURE_PREFIX + mac.hexdigest()


def verify_signature(ctx: dict):
    key = _key()
    if key is None:
        return None  # verification unavailable — caller decides policy
    sig = (ctx.get("issuance") or {}).get("countersignature")
    if not sig:
        return False
    expected = SIGNATURE_PREFIX + hmac.new(
        key, canon.canon(_unsigned(ctx)), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def set_digest(entries: list, label: str) -> str:
    """Digest of an adoption set — the issuer and the CLI verification side
    must agree on exactly this construction (coh-ctx-01)."""
    if not isinstance(entries, list):
        raise ValueError(f"{label} set must be a list")
    schema = schemacheck.load(f"{label}-entry.schema.json" if label == "baseline"
                              else "exception.schema.json")
    errs = [e for i, entry in enumerate(entries)
            for e in schemacheck.validate(entry, schema)]
    if errs:
        raise ValueError(f"invalid {label} set: " + "; ".join(errs[:5]))
    return canon.digest_obj("context/v1", {"kind": f"{label}-set",
                                           "entries": entries})


def load_stage_registry(path: str) -> dict:
    """repo -> {stage, owner, ...}. Stage is the authoritative adoption record."""
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError("stage registry must be an object keyed by repo")
    for repo, rec in data.items():
        for f in ("stage", "owner"):
            if not isinstance(rec, dict) or f not in rec:
                raise ValueError(f"stage registry {repo!r}: missing {f!r}")
        if rec["stage"] not in (0, 1, 2, 3, 4):
            raise ValueError(f"stage registry {repo!r}: bad stage {rec['stage']!r}")
    return data


def effective_stage(registry: dict, repo: str, requested: int = None) -> int:
    """Authoritative stage; a weaker request is refused (coh-ctx-02)."""
    rec = registry.get(repo)
    if rec is None:
        raise ValueError(f"no adoption record for {repo!r}")
    stage = rec["stage"]
    if requested is not None and requested < stage:
        raise ValueError(
            f"requested stage {requested} is weaker than the authoritative "
            f"stage {stage} for {repo!r} (coh-ctx-02)")
    return stage


def issue_context(ctx_dir: str, policy_dir: str, *, repo: str,
                  registry_path: str, evaluation_time: str,
                  requested_stage: int = None,
                  execution_profile: str = "linux-amd64-v1",
                  baseline_set=None, exception_set=None,
                  capability_grants=None, captured_facts=None,
                  context_id: str = "pilot-context",
                  semantics: str = "fresh-promotion",
                  issuer: str = None,
                  signer_set=None) -> dict:
    """Issue a pilot evaluation context.

    Writes context.json into ctx_dir; baseline/exception sets into policy_dir
    (where the CLI's load_adoption_sets reads them). Raises ValueError on an
    unknown repo, a stage downgrade request, or an invalid set.

    `semantics: replay` re-runs a historical decision with the SAME trusted
    fields (evaluation_time/stage/sets) and is structurally labeled
    non-promotion-authorizing in the canonical payload (coh-ctx-03). A
    replay may not change the time, stage, or sets it replays.

    `signer_set`: optional path to a signer-set document; when provided,
    the context carries its digest (coh-ev-05).
    """
    if semantics not in ("fresh-promotion", "replay"):
        raise ValueError(f"invalid semantics {semantics!r}")
    registry = load_stage_registry(registry_path)
    stage = effective_stage(registry, repo, requested_stage)

    ctx_root = Path(ctx_dir)
    ctx_root.mkdir(parents=True, exist_ok=True)
    pol_root = Path(policy_dir)
    pol_root.mkdir(parents=True, exist_ok=True)

    baseline_digest = exception_digest = None
    if baseline_set is not None:
        baseline_digest = set_digest(baseline_set, "baseline")
        (pol_root / "baseline.json").write_bytes(canon.canon(baseline_set))
    if exception_set is not None:
        exception_digest = set_digest(exception_set, "exception")
        (pol_root / "exceptions.json").write_bytes(canon.canon(exception_set))

    signer_set_digest = None
    if signer_set is not None:
        signer_set_doc = attest.load_signer_set(signer_set)
        signer_set_digest = attest.signer_set_digest(signer_set_doc)

    ctx = {
        "api_version": "devgate.spec-coherence.context/v1",
        "context_id": context_id,
        "evaluation_time": evaluation_time,
        "stage": stage,
        "semantics": semantics,
        "baseline_set_digest": baseline_digest,
        "exception_set_digest": exception_digest,
        "signer_set_digest": signer_set_digest,
        "capability_grants": capability_grants or [],
        "captured_facts": captured_facts or [],
        "execution_profile": execution_profile,
        "supported_runners": [execution_profile],
        "issuance": {
            "issued_at": evaluation_time,
            "issuer": issuer or os.environ.get(CP_IDENTITY_ENV, "cp-stand-in"),
        },
    }
    if _key() is not None:
        ctx["issuance"]["countersignature"] = sign_context(ctx)
    payload = canon.canon(ctx)
    (ctx_root / "context.json").write_bytes(payload)
    # The request's context.expected_digest must be the digest context.load
    # will compute — that is the digest over the file bytes as parsed, not
    # the file's sha256.
    return {"context_digest": canon.digest_obj("context/v1", ctx),
            "stage": stage,
            "baseline_set_digest": baseline_digest,
            "exception_set_digest": exception_digest,
            "signed": "countersignature" in ctx["issuance"]}
