#!/usr/bin/env python3
# // spec: coh-oap-01, coh-oap-07, coh-oap-hard-04
"""OBSERVE-ONLY producer CLI for the `devgate.oap-evidence/v2` wire.

This emits ONE OR MORE v2 wire envelopes as newline-delimited JSON (NDJSON) on
stdout (or `--out`), so a co-located observe-only consumer — e.g. the
independent Go `cmd/oap-observer` receiver in the sibling
`openagentplatform-audit-plan` repository — can read them from a real pipe::

    python tools/oap_produce.py --all | oap-observer -dev-keys evidence/keys.json

It is NON-AUTHORIZING and NON-EFFECTING by construction. It produces bytes and
writes a local evidence bundle; it NEVER authorizes, executes, or acts on any
OAP effect, and it opens no socket or transport. A `verify_wire_envelope`-PASS
envelope is a mathematical + binding statement about fixed bytes — NOT
authenticity, NOT authorization, and NOT permission to act.

Envelope shape is exactly the contract-v2 wire object that
`hub.coherence.strict_parse.verify_wire_envelope` parses: canonical
`{"body":..,"signature":..}` bytes, one envelope per NDJSON line. No new shape
is invented. The valid envelope is built by the REAL producer path
(`hub.coherence.oap_v2_producer.produce` + the vetted Ed25519 provider); the
adversarial variants are the same real artifact deliberately mutated (forged
low-order signature, duplicated JSON key, wrong domain tag, out-of-window
timestamps, wrong audience/tenant) or produced over internally inconsistent
evidence (lying cross-link).

Scope honesty: this repo has no Go OAP receiver of its own. This CLI provides
the producer side of a local pipe only; it does NOT claim an end-to-end Go OAP
consumer path is exercised here.
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from hub.coherence import canon, ed25519_vetted, strict_parse  # noqa: E402
from hub.coherence.oap_v2_producer import produce  # noqa: E402

NON_AUTHORIZING = True

# --- deterministic fixture inputs (no secrets; a fixed dev seed) ------------
SEED = bytes([0x11]) * 32
# texture of the classic Ed25519 identity/low-order encoding (y=1, x=0).
IDENTITY_PUBLIC = bytes.fromhex("01" + "00" * 31)

SUBJECT_DIGEST = "sha256:" + "a" * 64
POLICY_DIGEST = "sha256:" + "b" * 64
CONTEXT_DIGEST = "sha256:" + "c" * 64
EVALUATOR_DIGEST = "sha256:" + "d" * 64
OPENSPEC_DIGEST = "sha256:" + "e" * 64

REFERENCE_TIME = "2026-10-05T12:01:00Z"
ISSUED = "2026-10-05T12:00:00Z"
EXPIRES = "2026-10-05T12:04:00Z"
EXPIRED_ISSUED = "2026-10-05T11:00:00Z"
EXPIRED_EXPIRES = "2026-10-05T11:04:00Z"
VALID_FROM = "2026-10-01T00:00:00Z"
VALID_UNTIL = "2027-01-01T00:00:00Z"

PRODUCER_ID = "devgate-instance-1"
AUDIENCE = "oap-observer"
TENANT = "fixture-project"

BASE_BODY = {
    "producer_id": PRODUCER_ID,
    "consumer_audience": AUDIENCE,
    "tenant_or_project_id": TENANT,
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

#: Emitted case names, in emission order. `replayed-jti` emits two lines.
CASES = (
    "valid",
    "identity-low-order-forgery",
    "duplicate-key",
    "wrong-domain-tag",
    "expired",
    "wrong-audience",
    "wrong-tenant",
    "lying-cross-link",
    "replayed-jti",
)


def build_bundle():
    """Internally cross-consistent payload/result/manifest/attestation bytes.

    Fixed literals only, so the emitted artifact is byte-identical on any host.
    The valid case's observer cross-binding stage checks the wiring below.
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
    return {
        "payload": payload,
        "result": result,
        "manifest": manifest,
        "attestation": attestation,
        "result_doc": result_doc,
        "manifest_doc": manifest_doc,
    }


def _valid_raw(bundle):
    return produce(BASE_BODY, payload=bundle["payload"], result=bundle["result"],
                   evidence_manifest=bundle["manifest"],
                   attestation=bundle["attestation"], seed=SEED)


def _sign_alt_body(body, seed, signed_bytes_override=None):
    public = ed25519_vetted.public_key(seed)
    message = strict_parse.signed_bytes(body) if signed_bytes_override is None \
        else signed_bytes_override
    return canon.canon({
        "body": body,
        "signature": {"algorithm": "Ed25519",
                      "key_id": strict_parse.key_id_for(public),
                      "value": "ed25519:" + ed25519_vetted.sign(seed, message).hex()},
    })


def build_case(name, bundle):
    """Return the list of NDJSON envelope byte-strings for one case name.

    Every returned value is the exact contract-v2 wire object; `replayed-jti`
    returns the same valid artifact twice so a consumer's replay guard can see
    the second sighting as a duplicate.
    """
    valid = _valid_raw(bundle)
    body = strict_parse.parse_envelope(valid)["body"]

    if name == "valid":
        return [valid]

    if name == "identity-low-order-forgery":
        forged = "ed25519:" + (IDENTITY_PUBLIC + bytes(32)).hex()
        return [canon.canon({
            "body": body,
            "signature": {"algorithm": "Ed25519",
                          "key_id": strict_parse.key_id_for(IDENTITY_PUBLIC),
                          "value": forged},
        })]

    if name == "duplicate-key":
        return [valid.replace(b'"signature":',
                              b'"body":{},"signature":', 1)]

    if name == "wrong-domain-tag":
        wrong_tag = b"devgate.oap-evidence/v0" + b"\x00" + canon.canon(body)
        return [_sign_alt_body(body, SEED, signed_bytes_override=wrong_tag)]

    if name == "expired":
        return [produce(dict(BASE_BODY, issued_at=EXPIRED_ISSUED,
                             expires_at=EXPIRED_EXPIRES),
                        payload=bundle["payload"], result=bundle["result"],
                        evidence_manifest=bundle["manifest"],
                        attestation=bundle["attestation"], seed=SEED)]

    if name == "wrong-audience":
        return [produce(dict(BASE_BODY, consumer_audience="other-audience"),
                        payload=bundle["payload"], result=bundle["result"],
                        evidence_manifest=bundle["manifest"],
                        attestation=bundle["attestation"], seed=SEED)]

    if name == "wrong-tenant":
        return [produce(dict(BASE_BODY, tenant_or_project_id="other-project"),
                        payload=bundle["payload"], result=bundle["result"],
                        evidence_manifest=bundle["manifest"],
                        attestation=bundle["attestation"], seed=SEED)]

    if name == "lying-cross-link":
        tampered_doc = dict(bundle["result_doc"])
        tampered_doc["subject_digest"] = "sha256:" + "9" * 64
        tampered_result = canon.canon(tampered_doc)
        return [produce(BASE_BODY, payload=bundle["payload"],
                        result=tampered_result,
                        evidence_manifest=bundle["manifest"],
                        attestation=bundle["attestation"], seed=SEED)]

    if name == "replayed-jti":
        return [valid, valid]

    raise ValueError(f"unknown case: {name}")


def build_all(names):
    """Yield (case_name, envelope_bytes) for each requested case, in order."""
    bundle = build_bundle()
    for name in names:
        for raw in build_case(name, bundle):
            yield name, raw


def _trust_doc(audience=AUDIENCE):
    public = ed25519_vetted.public_key(SEED)
    return {"snapshot_time": REFERENCE_TIME,
            "entries": [{
                "producer_id": PRODUCER_ID,
                "key_id": strict_parse.key_id_for(public),
                "public_key": public.hex(),
                "audience": audience,
                "direction": "devgate-to-oap",
                "valid_from": VALID_FROM,
                "valid_until": VALID_UNTIL,
                "revoked": False,
                "revocation_version": 7,
            }]}


def write_evidence(dir_path):
    """Write the companion bundle a full observer run needs. Local files only."""
    out = Path(dir_path)
    out.mkdir(parents=True, exist_ok=True)
    bundle = build_bundle()
    (out / "payload.bin").write_bytes(bundle["payload"])
    (out / "result.bin").write_bytes(bundle["result"])
    (out / "manifest.bin").write_bytes(bundle["manifest"])
    (out / "attestation.bin").write_bytes(bundle["attestation"])
    (out / "keys.json").write_text(
        json.dumps(_trust_doc(), separators=(",", ":")),
        encoding="utf-8")
    expected = dict(BASE_BODY, direction="devgate-to-oap")
    (out / "expected.json").write_text(
        json.dumps(expected, indent=2, sort_keys=True), encoding="utf-8")
    (out / "reference-time.txt").write_text(REFERENCE_TIME + "\n",
                                            encoding="utf-8")


DOC_LINE = (
    "oap_produce: OBSERVE-ONLY producer for devgate.oap-evidence/v2; emits "
    "NDJSON wire envelopes; NON_AUTHORIZING; never authorizes or executes.")


def _parser():
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog=DOC_LINE)
    parser.add_argument("--case", action="append", choices=CASES,
                        help="emit one named case (repeatable)")
    parser.add_argument("--all", action="store_true",
                        help="emit one of every case, in a fixed order")
    parser.add_argument("--out", default=None,
                        help="write NDJSON here instead of stdout")
    parser.add_argument("--evidence-dir", default=None,
                        help="also write the companion evidence/keys/expected "
                             "bundle a full observer run needs (local files only)")
    parser.add_argument("--observe-only", action="store_true",
                        help="accepted framing flag; the CLI is always "
                             "observe-only and non-authorizing")
    parser.add_argument("--doc", action="store_true",
                        help="print the observe-only framing line to stderr")
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    if args.doc:
        print(DOC_LINE, file=sys.stderr)

    names = list(CASES) if args.all else list(args.case or [])
    if not names:
        # Nothing selected: emit the valid case so a bare pipe produces output.
        names = ["valid"]

    if not ed25519_vetted.AVAILABLE:
        print("NOT_RUN: vetted Ed25519 provider unavailable", file=sys.stderr)
        return 2

    lines = [raw for _name, raw in build_all(names)]
    payload = b"".join(line + b"\n" for line in lines)

    if args.evidence_dir:
        write_evidence(args.evidence_dir)

    if args.out:
        Path(args.out).write_bytes(payload)
    else:
        sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
