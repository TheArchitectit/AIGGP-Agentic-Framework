#!/usr/bin/env python3
# // spec: coh-oap-01, coh-oap-07, coh-oap-hard-04
"""Deterministic reference-vector builder for the `devgate.oap-evidence/v2` wire.

This is the Python *reference* producer/verifier for the cross-language golden
vectors frozen at::

    openspec/changes/add-oap-evidence-consumer/vectors/oap-evidence-v2-vectors.json

Scope and honesty (read before trusting anything here):

  - The vectors are produced BY THE EXISTING PYTHON CODE (the real
    `hub.coherence.oap_v2_producer.produce` and the real
    `hub.coherence.strict_parse.verify_wire_envelope` /
    `hub.coherence.oap_observer.observe`). Nothing is re-implemented locally,
    so a regeneration exercises the real code path, not a copy of it.
  - The eventual independent Go OAP receiver DOES NOT EXIST YET. These vectors
    are a fixed target for it, not evidence that one consumes them. A Go
    implementation copying these results is **NOT_EXERCISED**.
  - Everything here is NON-AUTHORIZING / observe-only. A passing vector is a
    mathematical + binding verdict over fixed bytes; it is not authenticity,
    not authorization, and grants no OAP effect.

Run to regenerate::

    python tests/fixtures/oap/oap_vectors.py
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from hub.coherence import canon, ed25519_vetted, oap_observer, strict_parse
from hub.coherence.oap_v2_producer import produce
from hub.coherence.replay_guard import InMemoryReplayBackend, ReplayGuard
from hub.coherence.trust_store import TrustStore, digest_of

# --- frozen fixture inputs -------------------------------------------------
SEED = bytes([0x11]) * 32
# texture of the classic Ed25519 identity/low-order encoding (y=1, x=0).
IDENTITY_PUBLIC = bytes.fromhex("01" + "00" * 31)

SUBJECT_DIGEST = "sha256:" + "a" * 64
POLICY_DIGEST = "sha256:" + "b" * 64
CONTEXT_DIGEST = "sha256:" + "c" * 64
EVALUATOR_DIGEST = "sha256:" + "d" * 64
OPENSPEC_DIGEST = "sha256:" + "e" * 64

NOW = "2026-10-05T12:01:00Z"
ISSUED = "2026-10-05T12:00:00Z"
EXPIRES = "2026-10-05T12:04:00Z"
VALID_FROM = "2026-10-01T00:00:00Z"
VALID_UNTIL = "2027-01-01T00:00:00Z"

BASE_BODY = {
    "producer_id": "devgate-instance-1",
    "consumer_audience": "oap-observer",
    "tenant_or_project_id": "fixture-project",
    "subject_kind": "source-tree",
    "subject_digest": SUBJECT_DIGEST,
    "request_id": "request-001",
    "evaluation_id": "evaluation-001",
    "nonce": "nonce-001",
    "idempotency_key": "idempotency-001",
    "issued_at": ISSUED,
    "expires_at": EXPIRES,
    "policy_digest": POLICY_DIGEST,
    "context_digest": CONTEXT_DIGEST,
    "evaluator_digest": EVALUATOR_DIGEST,
    "native_decision": "PASS",
    "native_exit_code": 0,
    "semantics": "fresh-promotion",
    "native_status": "PASS",
    "native_reason": "all required assertions satisfied",
}


def _public_key():
    return ed25519_vetted.public_key(SEED)


def _evidence_bundle():
    """Internally cross-consistent payload/result/manifest/attestation bytes.

    Built from fixed literals so regeneration is byte-identical on any host.
    The v2 producer commits to these exact bytes; the observer's cross-binding
    stage then checks result<->manifest<->attestation<->body wiring.
    """
    manifest_doc = {
        "api_version": "devgate.spec-coherence.evidence/v1",
        "objects": [],
    }
    manifest = canon.canon(manifest_doc)
    manifest_obj_digest = canon.digest_obj("evidence-manifest/v1", manifest_doc)

    result_doc = {
        "api_version": "devgate.spec-coherence.result/v1",
        "decision": "PASS",
        "semantics": "fresh-promotion",
        "subject_digest": SUBJECT_DIGEST,
        "openspec_digest": OPENSPEC_DIGEST,
        "policy_digest": POLICY_DIGEST,
        "context_digest": CONTEXT_DIGEST,
        "evaluator_image_digest": EVALUATOR_DIGEST,
        "platform": "fixture",
        "evidence_manifest_digest": manifest_obj_digest,
    }
    result = canon.canon(result_doc)

    attestation_doc = {
        "api_version": "devgate.spec-coherence.attestation/v1",
        "statement_digest": canon.digest_bytes("decision/v1", result),
        "bound": {
            "subject_digest": SUBJECT_DIGEST,
            "openspec_digest": OPENSPEC_DIGEST,
            "policy_digest": POLICY_DIGEST,
            "context_digest": CONTEXT_DIGEST,
            "evaluator_image_digest": EVALUATOR_DIGEST,
            "evidence_manifest_digest": manifest_obj_digest,
        },
        "signer": {"key_id": "ed25519:" + "0" * 64, "identity": "devgate-attestor"},
        "signature": "hmac-sha256:" + "0" * 64,
    }
    attestation = canon.canon(attestation_doc)

    payload = canon.canon({"subject_digest": SUBJECT_DIGEST})
    return payload, result, manifest, attestation, result_doc


def _trust_doc(entries, snapshot_time=NOW):
    return {"snapshot_time": snapshot_time, "entries": entries}


def _default_entry(public_hex, key_id, audience="oap-observer"):
    return {
        "producer_id": "devgate-instance-1",
        "key_id": key_id,
        "public_key": public_hex,
        "audience": audience,
        "direction": "devgate-to-oap",
        "valid_from": VALID_FROM,
        "valid_until": VALID_UNTIL,
        "revoked": False,
        "revocation_version": 7,
    }


def _trust_store(entries, tmp_root, name):
    path = tmp_root / f"trust-{name}.json"
    path.write_text(json.dumps(_trust_doc(entries), separators=(",", ":")),
                    encoding="utf-8")
    return TrustStore.load(path)


class _Fixture:
    """One deterministic producer run plus the trust material it needs."""

    def __init__(self, tmp_root):
        self.tmp_root = tmp_root
        self.public = _public_key()
        self.key_id = strict_parse.key_id_for(self.public)
        (self.payload, self.result, self.manifest, self.attestation,
         self.result_doc) = _evidence_bundle()
        self.raw = produce(BASE_BODY, payload=self.payload, result=self.result,
                           evidence_manifest=self.manifest,
                           attestation=self.attestation, seed=SEED)
        self.body = strict_parse.parse_envelope(self.raw)["body"]
        self.signed_bytes = strict_parse.signed_bytes(self.body)
        self.expected = dict(BASE_BODY, direction="devgate-to-oap")
        self.stores = {
            "default": _trust_store(
                [_default_entry(self.public.hex(), self.key_id)], tmp_root,
                "default"),
            "identity-key": _trust_store(
                [_default_entry(IDENTITY_PUBLIC.hex(),
                                strict_parse.key_id_for(IDENTITY_PUBLIC))],
                tmp_root, "identity-key"),
            "other-audience": _trust_store(
                [_default_entry(self.public.hex(), self.key_id,
                                audience="other-audience")],
                tmp_root, "other-audience"),
        }


def _envelope_case(name, category, description, raw, fixture, *, store="default",
                   reference_time=NOW, audience=None, payload=None, result=None,
                   manifest=None, attestation=None, note=None):
    """Verify one raw artifact through the real wire verifier and record it."""
    ok, reason = strict_parse.verify_wire_envelope(
        raw, fixture.stores[store], reference_time=reference_time,
        payload=fixture.payload if payload is None else payload,
        result=fixture.result if result is None else result,
        evidence_manifest=fixture.manifest if manifest is None else manifest,
        attestation=fixture.attestation if attestation is None else attestation,
        audience=audience)
    signature = None
    try:
        signature = strict_parse.parse_envelope(raw)["signature"]["value"]
    except strict_parse.StrictParseError:
        pass
    case = {
        "name": name,
        "category": category,
        "api": "hub.coherence.strict_parse.verify_wire_envelope",
        "description": description,
        "canonical_bytes_hex": raw.hex(),
        "signature_hex": signature,
        "signing_public_key_hex": fixture.public.hex(),
        "key_id": fixture.key_id,
        "signed_bytes_hex": fixture.signed_bytes.hex(),
        "reference_time": reference_time,
        "audience": audience,
        "trust_store": store,
        "expected": {"ok": ok, "reason": reason},
    }
    if note:
        case["note"] = note
    return case


def _observe_case(name, category, description, raw, fixture, *, store="default",
                  reference_time=NOW, expected=None, now=1_000_000.0,
                  replay_guard=None, payload=None, result=None, manifest=None,
                  attestation=None, note=None):
    """Verify one raw artifact through the real observe-only consumer."""
    observation = oap_observer.observe(
        raw, fixture.stores[store],
        fixture.expected if expected is None else expected,
        reference_time=reference_time,
        payload=fixture.payload if payload is None else payload,
        result=fixture.result if result is None else result,
        evidence_manifest=fixture.manifest if manifest is None else manifest,
        attestation=fixture.attestation if attestation is None else attestation,
        replay_guard=replay_guard or ReplayGuard(InMemoryReplayBackend()),
        operation="observe-coherence", now=now, revocation_version=7)
    signature = strict_parse.parse_envelope(raw)["signature"]["value"]
    case = {
        "name": name,
        "category": category,
        "api": "hub.coherence.oap_observer.observe",
        "description": description,
        "canonical_bytes_hex": raw.hex(),
        "signature_hex": signature,
        "signing_public_key_hex": fixture.public.hex(),
        "key_id": fixture.key_id,
        "signed_bytes_hex": strict_parse.signed_bytes(
            strict_parse.parse_envelope(raw)["body"]).hex(),
        "reference_time": reference_time,
        "trust_store": store,
        "expected": {"ok": observation.accepted, "reason": observation.reason},
    }
    if note:
        case["note"] = note
    return case


def build_vectors(tmp_root):
    """Construct the full language-neutral reference-vector document."""
    fixture = _Fixture(tmp_root)
    cases = []

    cases.append(_envelope_case(
        "valid_artifact", "valid",
        "A real v2 artifact produced by oap_v2_producer; signature, trust and "
        "all four evidence digests verify.", fixture.raw, fixture,
        audience="oap-observer"))

    # --- forgery: identity / low-order public key --------------------------
    forged_sig = "ed25519:" + (IDENTITY_PUBLIC + bytes(32)).hex()
    forged_raw = canon.canon({
        "body": fixture.body,
        "signature": {"algorithm": "Ed25519",
                      "key_id": strict_parse.key_id_for(IDENTITY_PUBLIC),
                      "value": forged_sig},
    })
    cases.append(_envelope_case(
        "identity_low_order_key_forgery", "forgery",
        "Artifact signed with the identity (order-1) public key and the "
        "classic R=identity/S=0 forgery; the strict verifier rejects the "
        "low-order point.", forged_raw, fixture, store="identity-key",
        audience="oap-observer",
        note="receiver reason is signature-mismatch: the low-order A point is "
             "refused before the RFC 8032 equation is even evaluated"))

    # --- structural: duplicate JSON key ------------------------------------
    duplicate_raw = fixture.raw.replace(b'"signature":', b'"body":{},"signature":', 1)
    cases.append(_envelope_case(
        "duplicate_json_key", "structural",
        "Same body with a duplicated top-level key; duplicate keys are "
        "rejected at every depth before canonicalization.", duplicate_raw,
        fixture, audience="oap-observer",
        note="expected.ok is False at the parse stage"))

    # --- wrong domain-separation tag ---------------------------------------
    wrong_tag_signed = b"devgate.oap-evidence/v0" + b"\x00" + canon.canon(fixture.body)
    wrong_tag_raw = canon.canon({
        "body": fixture.body,
        "signature": {"algorithm": "Ed25519", "key_id": fixture.key_id,
                      "value": "ed25519:" + ed25519_vetted.sign(
                          SEED, wrong_tag_signed).hex()},
    })
    cases.append(_envelope_case(
        "wrong_domain_separation_tag", "forgery",
        "A genuine signature over the wrong domain tag. The receiver always "
        "recomputes `devgate.oap-evidence/v2` + 0x00 + canonical body, so the "
        "signature cannot match.", wrong_tag_raw, fixture,
        audience="oap-observer",
        note="signed_bytes_hex is what the RECEIVER recomputes; the presented "
             "signature commits to a different domain tag"))

    # --- timestamp window --------------------------------------------------
    cases.append(_envelope_case(
        "expired_timestamp", "window",
        "Reference time is past `expires_at`; the envelope is expired.",
        fixture.raw, fixture, reference_time="2026-10-05T12:05:00Z",
        audience="oap-observer"))
    cases.append(_envelope_case(
        "not_yet_valid_timestamp", "window",
        "Reference time is before `issued_at`; the envelope is not yet valid.",
        fixture.raw, fixture, reference_time="2026-10-05T11:59:00Z",
        audience="oap-observer"))
    cases.append(_envelope_case(
        "key_out_of_window", "window",
        "Reference time is past the signing key's `valid_until`.",
        fixture.raw, fixture, reference_time="2027-06-01T00:00:00Z",
        audience="oap-observer"))

    # --- audience / tenant -------------------------------------------------
    cases.append(_envelope_case(
        "wrong_audience", "context",
        "The receiver expects a different audience than the signed one.",
        fixture.raw, fixture, audience="other-audience"))
    cases.append(_envelope_case(
        "key_audience_mismatch", "context",
        "The provisioned key entry is scoped to a different audience than the "
        "envelope declares.", fixture.raw, fixture, store="other-audience",
        audience=None))

    # --- lying digest / cross-link -----------------------------------------
    cases.append(_envelope_case(
        "lying_digest", "binding",
        "A valid signature over a body whose `result_digest` does not match "
        "the supplied result bytes.", fixture.raw, fixture,
        audience="oap-observer", result=fixture.result + b"x"))

    tampered_result_doc = dict(fixture.result_doc)
    tampered_result_doc["subject_digest"] = "sha256:" + "9" * 64
    tampered_result = canon.canon(tampered_result_doc)
    tampered_raw = produce(BASE_BODY, payload=fixture.payload,
                           result=tampered_result,
                           evidence_manifest=fixture.manifest,
                           attestation=fixture.attestation, seed=SEED)
    cases.append(_observe_case(
        "lying_cross_link", "binding",
        "Wire digests all match their bytes, but the supplied result's "
        "`subject_digest` disagrees with the signed body; the observer's "
        "cross-binding stage rejects it.", tampered_raw, fixture,
        result=tampered_result))

    # --- wrong tenant ------------------------------------------------------
    wrong_tenant_expected = dict(fixture.expected,
                                 tenant_or_project_id="other-project")
    cases.append(_observe_case(
        "wrong_tenant", "context",
        "The receiver's independently provisioned tenant/project disagrees "
        "with the signed `tenant_or_project_id`.", fixture.raw, fixture,
        expected=wrong_tenant_expected))

    # --- replayed jti ------------------------------------------------------
    replay_guard = ReplayGuard(InMemoryReplayBackend())
    first = oap_observer.observe(
        fixture.raw, fixture.stores["default"], fixture.expected,
        reference_time=NOW, payload=fixture.payload, result=fixture.result,
        evidence_manifest=fixture.manifest, attestation=fixture.attestation,
        replay_guard=replay_guard, operation="observe-coherence",
        now=1_000_000.0, revocation_version=7)
    second = oap_observer.observe(
        fixture.raw, fixture.stores["default"], fixture.expected,
        reference_time=NOW, payload=fixture.payload, result=fixture.result,
        evidence_manifest=fixture.manifest, attestation=fixture.attestation,
        replay_guard=replay_guard, operation="observe-coherence",
        now=1_000_000.0, revocation_version=7)
    cases.append({
        "name": "replayed_jti",
        "category": "replay",
        "api": "hub.coherence.oap_observer.observe + hub.coherence.replay_guard.ReplayGuard",
        "description": "The same idempotency key/scope is replayed; the first "
                       "sighting is admitted (still non-authorizing), the "
                       "second is a duplicate denial.",
        "canonical_bytes_hex": fixture.raw.hex(),
        "signature_hex": strict_parse.parse_envelope(
            fixture.raw)["signature"]["value"],
        "signing_public_key_hex": fixture.public.hex(),
        "key_id": fixture.key_id,
        "signed_bytes_hex": fixture.signed_bytes.hex(),
        "reference_time": NOW,
        "trust_store": "default",
        "expected": {
            "sequence": [
                {"call": 1, "ok": first.accepted, "reason": first.reason},
                {"call": 2, "ok": second.accepted, "reason": second.reason},
            ],
        },
    })

    return {
        "api_version": "devgate.oap-evidence.reference-vectors/v1",
        "contract_version": "devgate.oap-evidence/v2",
        "status": {
            "non_authorizing": True,
            "observe_only": True,
            "go_receiver": "NOT_EXERCISED",
            "produced_by": (
                "hub.coherence.oap_v2_producer + hub.coherence.strict_parse "
                "+ hub.coherence.oap_observer (Python reference)"),
            "note": (
                "Python-produced reference vectors. No independent Go OAP "
                "receiver exists yet; consumption of these vectors by a Go "
                "implementation is NOT_EXERCISED. Every verdict is "
                "NON-AUTHORIZING and grants no OAP effect."),
        },
        "fixture": {
            "signing_public_key_hex": fixture.public.hex(),
            "signing_key_id": fixture.key_id,
            "reference_time": NOW,
            "expected_audience": "oap-observer",
            "expected_tenant_or_project_id": "fixture-project",
            "trust_stores": {
                name: _trust_doc(store.entries, snapshot_time=NOW)
                for name, store in fixture.stores.items()
            },
            "ai_must_not": (
                "treat any expected.ok = true as authorization, as a "
                "production effect, or as evidence a receiver consumed it"),
        },
        "case_count": len(cases),
        "cases": cases,
    }


def dumps(vectors) -> bytes:
    """Canonical-ish, human-readable serialization used for the committed file."""
    return (json.dumps(vectors, indent=2, sort_keys=True, ensure_ascii=True)
            + "\n").encode("utf-8")


def main(argv=None) -> int:
    import tempfile

    if not ed25519_vetted.AVAILABLE:
        print("NOT_RUN: vetted Ed25519 provider unavailable; refusing to "
              "regenerate vectors", file=sys.stderr)
        return 2
    out = (REPO / "openspec" / "changes" / "add-oap-evidence-consumer"
           / "vectors" / "oap-evidence-v2-vectors.json")
    with tempfile.TemporaryDirectory() as tmp:
        payload = dumps(build_vectors(Path(tmp)))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(payload)
    print(f"wrote {out} ({len(payload)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
