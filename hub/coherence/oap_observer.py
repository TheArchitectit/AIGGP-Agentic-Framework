# // spec: coh-oap-hard-04, coh-oap-hard-06
"""Independent, local observe-only v2 consumer conformance boundary.

This is deliberately not an OAP service or authorization API. It consumes raw
bytes, independently provisioned trust, expected receiver context, exact
sealed bytes, and receiver-owned replay state, then returns an observation.
Every successful result remains non-authorizing.
"""
import json
from dataclasses import dataclass

from . import canon, schemacheck, strict_parse
from .replay_guard import ReplayGuard, ReplayScope
from .trust_store import TrustStore, digest_of

NON_AUTHORIZING = True


@dataclass(frozen=True)
class Observation:
    accepted: bool
    reason: str
    replay_status: str | None = None


def _context_check(body, expected):
    fields = (
        "producer_id", "consumer_audience", "tenant_or_project_id",
        "subject_kind", "subject_digest", "policy_digest", "context_digest",
        "evaluator_digest", "direction",
    )
    for field in fields:
        if body[field] != expected.get(field):
            return f"context-mismatch:{field}"
    if body["native_decision"] != expected.get("native_decision", body["native_decision"]):
        return "context-mismatch:native_decision"
    if body["semantics"] != expected.get("semantics", body["semantics"]):
        return "context-mismatch:semantics"
    return None


def _cross_bind(body, result, manifest, attestation):
    try:
        result_doc = json.loads(result.decode("utf-8"))
        manifest_doc = json.loads(manifest.decode("utf-8"))
        attestation_doc = json.loads(attestation.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "evidence-malformed"
    if not isinstance(result_doc, dict) or not isinstance(manifest_doc, dict) \
            or not isinstance(attestation_doc, dict):
        return "evidence-malformed"
    if schemacheck.validate(attestation_doc,
                            schemacheck.load("attestation.schema.json")):
        return "attestation-schema-invalid"
    if result_doc.get("decision") != body["native_decision"]:
        return "result-decision-mismatch"
    if result_doc.get("semantics") != body["semantics"]:
        return "result-semantics-mismatch"
    for field, result_field in (
            ("subject_digest", "subject_digest"),
            ("policy_digest", "policy_digest"),
            ("context_digest", "context_digest"),
            ("evaluator_digest", "evaluator_image_digest")):
        if result_doc.get(result_field) != body[field]:
            return f"result-binding-mismatch:{field}"
    manifest_object_digest = canon.digest_obj("evidence-manifest/v1", manifest_doc)
    if result_doc.get("evidence_manifest_digest") != manifest_object_digest:
        return "result-binding-mismatch:evidence_manifest_digest"
    if body["evidence_manifest_digest"] != digest_of(manifest):
        return "manifest-digest-mismatch"
    if body["result_digest"] != digest_of(result):
        return "result-digest-mismatch"
    if body["attestation_digest"] != digest_of(attestation):
        return "attestation-digest-mismatch"
    if canon.digest_bytes("decision/v1", result) != attestation_doc.get("statement_digest"): 
        return "attestation-statement-mismatch"
    bound = attestation_doc.get("bound")
    if not isinstance(bound, dict):
        return "attestation-binding-malformed"
    for field, att_field in (
            ("subject_digest", "subject_digest"),
            ("policy_digest", "policy_digest"),
            ("context_digest", "context_digest"),
            ("evaluator_digest", "evaluator_image_digest")):
        if bound.get(att_field) != body[field]:
            return f"attestation-binding-mismatch:{field}"
    if bound.get("evidence_manifest_digest") != result_doc.get(
            "evidence_manifest_digest"):
        return "attestation-binding-mismatch:evidence_manifest_digest"
    return None


def observe(raw, trust_store: TrustStore, expected: dict, *, reference_time,
            payload: bytes, result: bytes, evidence_manifest: bytes,
            attestation: bytes, replay_guard: ReplayGuard,
            operation: str, now: float, revocation_version: int) -> Observation:
    """Observe one candidate through the consumer validation order.

    No branch authorizes an action. Replay admission is recorded as a
    non-authorizing observation and is only reached after all evidence checks.
    """
    ok, reason = strict_parse.verify_wire_envelope(
        raw, trust_store, reference_time=reference_time,
        payload=payload, result=result, evidence_manifest=evidence_manifest,
        attestation=attestation, audience=expected.get("consumer_audience"))
    if not ok:
        return Observation(False, reason)
    envelope = strict_parse.parse_envelope(raw)
    body = envelope["body"]
    reason = _context_check(body, expected)
    if reason:
        return Observation(False, reason)
    reason = _cross_bind(body, result, evidence_manifest, attestation)
    if reason:
        return Observation(False, reason)
    expected_exit = strict_parse.DECISION_EXIT_CODES[body["native_decision"]]
    if body["native_exit_code"] not in expected_exit:
        return Observation(False, "decision-exit-mismatch")
    if body["native_decision"] == "PASS" and body["native_status"] != "PASS":
        return Observation(False, "status-exit-mismatch")
    scope = ReplayScope(
        producer_id=body["producer_id"], tenant=body["tenant_or_project_id"],
        direction=body["direction"], audience=body["consumer_audience"],
        operation=operation, subject=body["subject_digest"],
        payload_digest=body["payload_digest"])
    replay_status, prior = replay_guard.submit(
        scope, idempotency_key=body["idempotency_key"],
        revocation_version=revocation_version, now=now)
    if replay_status != "admitted":
        return Observation(False, f"replay:{replay_status}", replay_status)
    replay_guard.record_outcome(body["idempotency_key"], "non-authorizing:observed")
    return Observation(True, "non-authorizing:observed", replay_status)


__all__ = ["NON_AUTHORIZING", "Observation", "observe"]
