#!/usr/bin/env python3
# // spec: coh-id-01, coh-id-05
"""Compute golden canonicalization and digest vectors for the coherence suite.

Deterministic: identical inputs on any host produce identical bytes and digests.
Run: python3 tests/fixtures/coherence/compute_golden.py
Regenerates vectors.json in place. The vectors are the compatibility contract
(coh-id-01 golden vectors scenario) — changing the profile must change them.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Restricted RFC 8785 profile (coh-id-01): sorted keys, no duplicates, UTF-8,
# integers within int64, single number format (integers only in the profile;
# floats are out of scope for v1 and rejected by the schema validators).

def canon(obj) -> bytes:
    """Canonical JSON per the restricted profile."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def digest(role_tag: str, payload: bytes) -> str:
    """Domain-separated digest: sha256 over tag bytes + 0x00 + payload (coh-id-05)."""
    h = hashlib.sha256()
    h.update(role_tag.encode("utf-8"))
    h.update(b"\x00")
    h.update(payload)
    return "sha256:" + h.hexdigest()


def main() -> int:
    lf = (HERE / "hello_lf.txt").read_bytes()
    crlf = (HERE / "hello_crlf.txt").read_bytes()
    decision_obj = json.loads((HERE / "canonical_sample.json").read_text(encoding="utf-8"))

    vectors = {
        "api_version": "devgate.spec-coherence.golden-vectors/v1",
        "profile": {
            "hash": "sha256",
            "canonical_json": "rfc8785-subset: sorted-keys, no-dup-keys, utf-8, int64-integers, no-floats",
            "file_hashing": "raw-bytes",
            "domain_separator": "<role-tag>\\x00<payload>",
        },
        "vectors": {
            # Raw-byte hashing: LF vs CRLF are different content (coh-id-01).
            "hello_lf_raw": digest("file/v1", lf),
            "hello_crlf_raw": digest("file/v1", crlf),
            "hello_lf_eq_crlf": digest("file/v1", lf) == digest("file/v1", crlf),
            # Canonical JSON over a sample decision-shaped object.
            "canonical_sample_bytes": canon(decision_obj).decode("utf-8"),
            "canonical_sample_digest": digest("decision/v1", canon(decision_obj)),
            # Domain separation: identical bytes in different roles differ.
            "role_file": digest("file/v1", lf),
            "role_subject": digest("subject-manifest/v1", lf),
            "roles_differ": digest("file/v1", lf) != digest("subject-manifest/v1", lf),
        },
    }

    out = json.dumps(vectors, indent=2, ensure_ascii=True) + "\n"
    (HERE / "vectors.json").write_text(out, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
