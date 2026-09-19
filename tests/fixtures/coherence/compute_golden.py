#!/usr/bin/env python3
# // spec: coh-id-01, coh-id-05
"""Compute golden canonicalization and digest vectors for the coherence suite.

Deterministic: identical inputs on any host produce identical bytes and digests.
Run: python3 tests/fixtures/coherence/compute_golden.py
Regenerates vectors.json in place. The vectors are the compatibility contract
(coh-id-01 golden vectors scenario) — changing the profile must change them.

Audit fix (harden-test-suite): this generator used to REIMPLEMENT canon and
digest locally, so regenerating the vectors exercised a copy of the logic, not
the real code path — exactly the "testing copies of the logic" anti-pattern
the README bans. It now imports `hub.coherence.canon`; its independence from
the test assertions is the cross-check, not a liability
(test_hub_coherence_golden.py asserts the REAL module against the frozen
vectors).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
sys.path.insert(0, str(REPO))

from hub.coherence import canon  # the REAL implementation, not a copy


def main() -> int:
    lf = (HERE / "hello_lf.txt").read_bytes()
    crlf = (HERE / "hello_crlf.txt").read_bytes()
    decision_obj = json.loads((HERE / "canonical_sample.json").read_text())

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
            "hello_lf_raw": canon.digest("file/v1", lf),
            "hello_crlf_raw": canon.digest("file/v1", crlf),
            "hello_lf_eq_crlf": canon.digest("file/v1", lf) == canon.digest("file/v1", crlf),
            # Canonical JSON over a sample decision-shaped object.
            "canonical_sample_bytes": canon.canon(decision_obj).decode("utf-8"),
            "canonical_sample_digest": canon.digest("decision/v1", canon.canon(decision_obj)),
            # Domain separation: identical bytes in different roles differ.
            "role_file": canon.digest("file/v1", lf),
            "role_subject": canon.digest("subject-manifest/v1", lf),
            "roles_differ": canon.digest("file/v1", lf) != canon.digest("subject-manifest/v1", lf),
        },
    }

    out = json.dumps(vectors, indent=2, ensure_ascii=True) + "\n"
    (HERE / "vectors.json").write_text(out)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
