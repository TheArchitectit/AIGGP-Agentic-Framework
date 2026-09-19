# // spec: coh-ev-01, coh-ev-05
"""Detached attestation: sign and verify bound statements.

Sealing order (coh-ev-01): immutable inputs -> evidence objects ->
evidence manifest -> canonical decision -> detached attestation ->
transport envelope. The canonical decision MUST NOT carry its own
attestation digest or signature; the attestation is a detached object.

Stage 0-1 observation/replay runs are non-promotion-authorizing:
signing is skipped and labeled. From Stage 2 fresh-promotion onward,
every promotion-authorizing result carries a signed detached attestation.
"""
import hashlib
import hmac
import json
import os
import re
import sys
from pathlib import Path

from . import canon, evidence, result, schemacheck

SIGNATURE_PREFIX = "hmac-sha256:"
SIGNER_KEY_ENV = "HUB_COHERENCE_SIGNER_KEY"
SIGNER_KEY_ID_ENV = "HUB_COHERENCE_SIGNER_KEY_ID"
SIGNER_IDENTITY_ENV = "HUB_COHERENCE_SIGNER_IDENTITY"
EVALUATOR_IMAGE_ENV = "HUB_COHERENCE_EVALUATOR_IMAGE_DIGEST"
SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent / \
    "openspec/changes/devgate-spec-coherence-service/schemas"
_EVIDENCE_DIR_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class AttestationError(RuntimeError):
    """attestation failure (exit-33 class)."""


def required(stage: int, semantics: str) -> bool:
    """True iff the run is promotion-authorizing and needs signing."""
    return stage >= 2 and semantics == "fresh-promotion"


def _key() -> bytes | None:
    raw = os.environ.get(SIGNER_KEY_ENV, "").strip()
    if not raw:
        return None
    try:
        return bytes.fromhex(raw)
    except ValueError:
        raise AttestationError("signer-key-not-configured") from None


def _signer_identity() -> str:
    return os.environ.get(SIGNER_IDENTITY_ENV, "pilot-signer")


def _signer_key_id() -> str:
    return os.environ.get(SIGNER_KEY_ID_ENV, "signer-1")


def sign(decision_bytes: bytes, identities: dict,
         evaluation_time: str) -> dict:
    """Build a signed attestation dict validating against the frozen
    attestation.schema.json. Uses only the evaluation context time."""
    key = _key()
    if key is None:
        raise AttestationError("signer-key-not-configured")
    evaluator_digest = identities.get("evaluator_image_digest")
    if evaluator_digest is None:
        raise AttestationError(
            "evaluator-image-digest-required-for-attestation")

    statement_digest = canon.digest_bytes("decision/v1", decision_bytes)
    bound = {
        "subject_digest": identities["subject_digest"],
        "openspec_digest": identities["openspec_digest"],
        "policy_digest": identities["policy_digest"],
        "context_digest": identities["context_digest"],
        "evaluator_image_digest": evaluator_digest,
        "evidence_manifest_digest": identities["evidence_manifest_digest"],
    }
    attestation = {
        "api_version": "devgate.spec-coherence.attestation/v1",
        "statement_digest": statement_digest,
        "bound": bound,
        "signer": {
            "key_id": _signer_key_id(),
            "identity": _signer_identity(),
        },
        "issued_at": evaluation_time,
    }
    unsigned = dict(attestation)
    unsigned.pop("signature", None)
    sig = SIGNATURE_PREFIX + hmac.new(
        key, canon.canon(unsigned), hashlib.sha256).hexdigest()
    attestation["signature"] = sig
    errs = schemacheck.validate(attestation, _load_schema("attestation.schema.json"))
    if errs:
        raise AttestationError("attestation-schema-validation-failed: " +
                               "; ".join(errs[:3]))
    return attestation


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text())


def verify(run_dir: str, signer_set: dict) -> tuple[bool, str]:
    """Verify a signed run. Returns (ok, reason).

    Fail-closed chain with distinct reason strings per check.
    """
    out = Path(run_dir)
    # 1. Load/parse artifacts
    result_path = out / "result.json"
    attestation_path = out / "attestation.json"
    manifest_path = out / "evidence-manifest.json"
    if not result_path.exists() or not attestation_path.exists() \
            or not manifest_path.exists():
        return False, "missing-artifact"
    try:
        result_doc = json.loads(result_path.read_text())
        attestation_doc = json.loads(attestation_path.read_text())
        manifest_doc = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError):
        return False, "unparseable-artifact"

    # 2-6. signer set membership, identity, revocation, window, signature
    signer_entry, reason = _check_signer(attestation_doc, signer_set)
    if reason:
        return False, reason
    ok, reason = _check_signature(attestation_doc, signer_entry)
    if not ok:
        return False, reason

    # 7. decision-digest-mismatch
    result_bytes = result_path.read_bytes()
    statement_digest = canon.digest_bytes("decision/v1", result_bytes)
    if statement_digest != attestation_doc.get("statement_digest"):
        return False, "decision-digest-mismatch"

    # 8. bound-digest-mismatch (six bound identities)
    result_parsed = json.loads(result_bytes)
    bound = attestation_doc.get("bound", {})
    for key in ("subject_digest", "openspec_digest", "policy_digest",
                "context_digest", "evaluator_image_digest",
                "evidence_manifest_digest"):
        if result_parsed.get(key) != bound.get(key):
            return False, f"bound-digest-mismatch:{key}"

    # 9. evidence tamper
    if not evidence.verify(run_dir, bound["evidence_manifest_digest"]):
        return False, "evidence-tamper"

    return True, "ok"


def _check_signer(attestation: dict, signer_set: dict) -> tuple:
    """Resolve the signing key against the approved set (coh-ev-05).

    Returns (signer_entry, reason) with reason None when every check passes:
    membership, identity, revocation, then validity window. Fail-closed.
    """
    signers = signer_set.get("signers", [])
    key_id = attestation.get("signer", {}).get("key_id", "")
    entry = next((s for s in signers if s.get("key_id") == key_id), None)
    if entry is None:
        return None, "signer-not-in-set"
    if entry.get("identity") != attestation.get("signer", {}).get("identity"):
        return None, "signer-identity-mismatch"
    if entry.get("revoked", False):
        return None, "signer-revoked"
    as_of = signer_set.get("as_of", "")
    if as_of < entry.get("valid_from", ""):
        return None, "signer-not-yet-valid"
    if as_of > entry.get("valid_until", ""):
        return None, "signer-expired"
    return entry, None


def _check_signature(attestation: dict, signer_entry: dict) -> tuple:
    """HMAC check over the canonical unsigned attestation."""
    unsigned = dict(attestation)
    unsigned.pop("signature", None)
    expected = SIGNATURE_PREFIX + hmac.new(
        bytes.fromhex(signer_entry["key"]),
        canon.canon(unsigned), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, attestation.get("signature", "")):
        return False, "signature-mismatch"
    return True, None


def verify_attestation(decision_bytes: bytes, attestation: dict,
                       signer_set: dict) -> tuple[bool, str]:
    """Verify an attestation dict against decision bytes and a signer set.

    Checks signer identity/revocation/expiry and the HMAC signature.
    Returns (ok, reason).
    """
    signer_entry, reason = _check_signer(attestation, signer_set)
    if reason:
        return False, reason
    ok, reason = _check_signature(attestation, signer_entry)
    if not ok:
        return False, reason
    statement_digest = canon.digest_bytes("decision/v1", decision_bytes)
    if statement_digest != attestation.get("statement_digest"):
        return False, "decision-digest-mismatch"
    return True, "ok"


def verify_run_cli(verify_dir: str, signer_set_path: str) -> int:
    """Consumer-side verification CLI entry: 0 verified / 1 failed / 2 malformed."""
    try:
        set_doc = load_signer_set(signer_set_path)
    except AttestationError as e:
        print(str(e), file=sys.stderr)
        return 2
    ok, reason = verify(verify_dir, set_doc)
    if ok:
        print(f"verification ok: {verify_dir}")
        return 0
    print(reason, file=sys.stderr)
    return 1


def load_signer_set(path: str) -> dict:
    """Parse + validate a signer-set document against the frozen schema."""
    try:
        doc = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise AttestationError(f"cannot load signer set: {e}") from None
    errs = schemacheck.validate(doc, _load_schema("signer-set.schema.json"))
    if errs:
        raise AttestationError(
            "invalid signer-set: " + "; ".join(errs[:5]))
    return doc


def signer_set_digest(set_doc: dict) -> str:
    """Digest of a signer-set document."""
    return canon.digest_obj("signer-set/v1", set_doc)


def seal_run(out_dir: str, res: dict, ledger: list, identities: dict,
             ev_digest: str, ctx: dict, blocked) -> int:
    """Emit the run's artifacts in acyclic sealing order (coh-ev-01):
    canonical decision first, detached attestation second, transport
    envelope last. Returns the decision's exit code."""
    stage = ctx["stage"]
    semantics = ctx.get("semantics", "fresh-promotion")
    payload = result.to_canonical(res)
    result.emit_with_fallback(out_dir, payload)
    _, code = result.decide(ledger, stage, blocked=blocked)

    attestation_path = None
    signed = False
    if required(stage, semantics):
        attestation = sign(
            payload, {**identities, "evidence_manifest_digest": ev_digest},
            ctx["evaluation_time"])
        # Same failure contract as the decision path (round-2 B1): an
        # unwritable output directory must yield the documented exit code,
        # never a raw traceback on the promotion-authorizing path.
        try:
            result.emit(f"{out_dir}/attestation.json",
                        result.to_canonical(attestation))
        except OSError as e:
            raise AttestationError(f"attestation-emit-failed:{e}") from e
        attestation_path = "attestation.json"
        signed = True

    emit_envelope(out_dir, decision=res["decision"], exit_code=code,
                  stage=stage, semantics=semantics, signed=signed,
                  attestation_path=attestation_path)
    return code


def emit_envelope(out_dir: str, *, decision: str, exit_code: int,
                   stage: int, semantics: str, signed: bool,
                   attestation_path: str | None) -> None:
    """Write the noncanonical transport envelope (last in sealing order).

    Same failure contract as the other seal writes: an unwritable location
    yields a documented exit code, never a raw traceback (round-2 B1).
    """
    envelope = {
        "api_version": "devgate.spec-coherence.envelope/v1",
        "decision": decision,
        "exit_code": exit_code,
        "stage": stage,
        "semantics": semantics,
        "attestation_required": required(stage, semantics),
        "signed": signed,
        "artifacts": {
            "result": "result.json",
            "evidence_manifest": "evidence-manifest.json",
            "attestation": attestation_path,
        },
    }
    try:
        result.emit(f"{out_dir}/run-envelope.json", canon.canon(envelope))
    except OSError as e:
        raise AttestationError(f"envelope-emit-failed:{e}") from e
