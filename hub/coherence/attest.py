# // spec: coh-ev-01, coh-ev-05
"""Detached attestation: sign and verify bound statements.

Two cooperating chains (both load-bearing; both stay):

  - Run-sealing (this module): sign() / seal_run() / verify_run() produce
    and check a signed run directory in acyclic order (coh-ev-01).
  - Detached S5 (attest_detached): attest() / verify() cover
    single-attestation consumers and the anti-rollback gate (coh-pol-02).

Both chains commit signature bytes to `_signed_statement` (attest_base), so
an attestation produced by either verifies under either verifier.

HONEST SCOPE: signatures are HMAC-SHA256. Keys come from
HUB_COHERENCE_SIGNER_KEYS (detached chain) or HUB_COHERENCE_SIGNER_KEY
(run-sealing chain) — stand-in scope until ADR-018 lands real key
management. Verification requires the signer set; an unconfigurable
verifier fails closed, never "accepts".
"""
import hashlib
import hmac
import json
import sys
from pathlib import Path

from . import canon, evidence, result, schemacheck
from .attest_base import (
    SIGNER_KEYS_ENV,
    SIGNER_KEY_ENV,
    SIGNER_KEY_ID_ENV,
    SIGNER_IDENTITY_ENV,
    EVALUATOR_IMAGE_ENV,
    SIGNATURE_PREFIX,
    AttestationError,
    key_id_for,
    signer_identity,
    signer_set_digest,
    _keys,
    _signed_statement,
)
from .attest_detached import (
    attest,
    check_anti_rollback,
    verify,
)

__all__ = [
    "AttestationError", "SIGNER_KEYS_ENV", "SIGNER_KEY_ENV",
    "SIGNER_KEY_ID_ENV", "SIGNER_IDENTITY_ENV", "EVALUATOR_IMAGE_ENV",
    "SIGNATURE_PREFIX",
    "attest", "check_anti_rollback", "emit_envelope",
    "key_id_for", "load_signer_set", "required", "seal_run", "sign",
    "signer_identity", "signer_set_digest", "verify", "verify_attestation",
    "verify_promotion", "verify_run", "verify_run_cli",
]


def required(stage: int, semantics: str) -> bool:
    """True iff the run is promotion-authorizing and needs signing."""
    return stage >= 2 and semantics == "fresh-promotion"


def _key() -> bytes | None:
    raw = __import__("os").environ.get(SIGNER_KEY_ENV, "").strip()
    if not raw:
        return None
    try:
        return bytes.fromhex(raw)
    except ValueError:
        raise AttestationError("signer-key-not-configured") from None


def _signer_identity() -> str:
    import os
    return os.environ.get(SIGNER_IDENTITY_ENV, "pilot-signer")


def _signer_key_id() -> str:
    import os
    return os.environ.get(SIGNER_KEY_ID_ENV, "signer-1")


def sign(decision_bytes: bytes, identities: dict,
         evaluation_time: str) -> dict:
    """Build a signed attestation dict validating against the frozen
    attestation.schema.json. Uses only the evaluation context time.

    Signature bytes are `_signed_statement(...)` so this chain's output
    verifies under both verify_run() and the S5 verify().
    """
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
    signer = {
        "key_id": _signer_key_id(),
        "identity": _signer_identity(),
    }
    issued_at = evaluation_time
    statement = _signed_statement(statement_digest, bound, signer, issued_at)
    sig = SIGNATURE_PREFIX + hmac.new(
        key, statement, hashlib.sha256).hexdigest()
    attestation = {
        "api_version": "devgate.spec-coherence.attestation/v1",
        "statement_digest": statement_digest,
        "bound": bound,
        "signer": signer,
        "issued_at": issued_at,
        "signature": sig,
    }
    errs = schemacheck.validate(attestation,
                                schemacheck.load("attestation.schema.json"))
    if errs:
        raise AttestationError("attestation-schema-validation-failed: " +
                               "; ".join(errs[:3]))
    return attestation


def verify_run(run_dir: str, signer_set: dict) -> tuple[bool, str]:
    """Verify a signed run. Returns (ok, reason).

    Fail-closed chain with distinct reason strings per check.
    """
    out = Path(run_dir)
    result_path = out / "result.json"
    attestation_path = out / "attestation.json"
    manifest_path = out / "evidence-manifest.json"
    if not result_path.exists() or not attestation_path.exists() \
            or not manifest_path.exists():
        return False, "missing-artifact"
    try:
        result_doc = json.loads(result_path.read_text(encoding="utf-8"))
        attestation_doc = json.loads(attestation_path.read_text(encoding="utf-8"))
        manifest_doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "unparseable-artifact"

    signer_entry, reason = _check_signer(attestation_doc, signer_set)
    if reason:
        return False, reason
    ok, reason = _check_signature(attestation_doc, signer_entry)
    if not ok:
        return False, reason

    result_bytes = result_path.read_bytes()
    statement_digest = canon.digest_bytes("decision/v1", result_bytes)
    if statement_digest != attestation_doc.get("statement_digest"):
        return False, "decision-digest-mismatch"

    result_parsed = json.loads(result_bytes)
    bound = attestation_doc.get("bound", {})
    for key in ("subject_digest", "openspec_digest", "policy_digest",
                "context_digest", "evaluator_image_digest",
                "evidence_manifest_digest"):
        if result_parsed.get(key) != bound.get(key):
            return False, f"bound-digest-mismatch:{key}"

    if not evidence.verify(run_dir, bound["evidence_manifest_digest"]):
        return False, "evidence-tamper"

    return True, "ok"


def verify_promotion(run_dir: str, signer_set: dict,
                     candidate_digest: str) -> tuple[bool, str]:
    """Verify a sealed run AND that it binds the candidate being promoted.

    coh-pol-07 scenario 2: a valid PASS attestation for subject digest D1
    presented for promotion of digest D2 MUST be refused.
    """
    ok, reason = verify_run(run_dir, signer_set)
    if not ok:
        return False, reason
    try:
        attestation = json.loads(
            (Path(run_dir) / "attestation.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "unparseable-artifact"
    bound = attestation.get("bound", {})
    if bound.get("subject_digest") != candidate_digest:
        return False, "candidate-digest-mismatch"
    return True, "ok"


def _check_signer(attestation: dict, signer_set: dict) -> tuple:
    """Resolve the signing key against the approved set (coh-ev-05).

    Returns (signer_entry, reason) with reason None when every check passes.
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
    """HMAC check over the shared signed-statement bytes."""
    signer = attestation.get("signer", {})
    statement = _signed_statement(attestation["statement_digest"],
                                  attestation["bound"], signer,
                                  attestation.get("issued_at"))
    expected = SIGNATURE_PREFIX + hmac.new(
        bytes.fromhex(signer_entry["key"]),
        statement, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, attestation.get("signature", "")):
        return False, "signature-mismatch"
    return True, None


def verify_attestation(decision_bytes: bytes, attestation: dict,
                       signer_set: dict) -> tuple[bool, str]:
    """Verify an attestation dict against decision bytes and a signer set."""
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
    ok, reason = verify_run(verify_dir, set_doc)
    if ok:
        print(f"verification ok: {verify_dir}")
        return 0
    print(reason, file=sys.stderr)
    return 1


def load_signer_set(path: str) -> dict:
    """Parse + validate a signer-set document against the frozen schema."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise AttestationError(f"cannot load signer set: {e}") from None
    errs = schemacheck.validate(doc, schemacheck.load("signer-set.schema.json"))
    if errs:
        raise AttestationError(
            "invalid signer-set: " + "; ".join(errs[:5]))
    return doc


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
        if _key() is not None:
            attestation = sign(
                payload, {**identities, "evidence_manifest_digest": ev_digest},
                ctx["evaluation_time"])
            try:
                result.emit(f"{out_dir}/attestation.json",
                            result.to_canonical(attestation))
            except OSError as e:
                raise AttestationError(f"attestation-emit-failed:{e}") from e
            attestation_path = "attestation.json"
            signed = True
        elif not _keys():
            # promotion-authorizing run and no chain can sign: fail closed,
            # never emit an unsigned attestation (stricter of the two
            # contracts; S5's test_stage2_no_signer_key_fails pins 33).
            raise AttestationError("signer-key-not-configured")

    emit_envelope(out_dir, decision=res["decision"], exit_code=code,
                  stage=stage, semantics=semantics, signed=signed,
                  attestation_path=attestation_path)
    return code


def emit_envelope(out_dir: str, *, decision: str, exit_code: int,
                  stage: int, semantics: str, signed: bool,
                  attestation_path: str | None) -> None:
    """Write the noncanonical transport envelope (last in sealing order)."""
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