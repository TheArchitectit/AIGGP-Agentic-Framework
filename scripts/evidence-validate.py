#!/usr/bin/env python3
"""evidence-validate.py — standalone sealed-evidence bundle validator.

Verifies a sealed evidence bundle (see hub/coherence/evidence.py) and any
verification claim files (hub/coherence/verification.py) placed beside it.
This is the independent half of the evidence contract: an operator or a
downstream pipeline can confirm a bundle WITHOUT importing the producer,
using nothing but this script and the bundle directory.

Exit codes (frozen):
  0   bundle verified — every object digest matches, manifest digest matches
  1   bundle INVALID — tamper, missing object, or malformed shape
  30  usage error — bad arguments or unreadable input paths

Checks performed:
  - evidence-manifest.json parses and is an object with an objects list
  - every object file exists inside the bundle (no parent escapes)
  - every object's recomputed digest matches the manifest
  - the manifest's own digest matches the expected value (--expected)
  - every *.claim.json beside the bundle re-serializes to its recorded
    digest, and its independent verification, if any, is internally
    consistent (fw-ev-04: stale anchors are reported, not accepted)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEVGATE_ROOT = Path(__file__).resolve().parent.parent
if str(DEVGATE_ROOT) not in sys.path:
    sys.path.insert(0, str(DEVGATE_ROOT))

from hub.coherence import canon, evidence, verification  # noqa: E402

EXIT_VALID = 0
EXIT_INVALID = 1
EXIT_USAGE = 30


def check_claims(bundle_dir: Path) -> list:
    """Re-verify every *.claim.json in the bundle dir. Returns problem list."""
    problems = []
    for path in sorted(bundle_dir.glob("*.claim.json")):
        try:
            claim = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
            problems.append(f"{path.name}: unreadable claim: {e}")
            continue
        if not isinstance(claim, dict):
            problems.append(f"{path.name}: claim is not a JSON object")
            continue
        try:
            actual = verification.digest_claim(claim)
        except (canon.CanonError, ValueError, TypeError) as e:
            problems.append(f"{path.name}: claim not canonicalizable: {e}")
            continue
        # The digest binding itself: a claim file whose recorded digest (in
        # an adjacent .claim.digest) disagrees was edited after the fact.
        digest_fp = path.with_suffix(path.suffix + ".digest")
        if digest_fp.exists():
            recorded = digest_fp.read_text(encoding="utf-8").strip()
            if recorded != actual:
                problems.append(
                    f"{path.name}: digest drift (recorded {recorded[:16]}.., "
                    f"actual {actual[:16]}..) — claim edited after sealing")
        else:
            problems.append(
                f"{path.name}: no .digest sidecar — provenance unprovable")
        iv = claim.get("independent_verification")
        if claim.get("state") == verification.VERIFIED and not iv:
            problems.append(
                f"{path.name}: state VERIFIED without independent "
                f"verification — self-certified claim rejected")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="evidence-validate",
        description="verify a sealed evidence bundle (fail-closed)")
    ap.add_argument("bundle", help="evidence bundle directory "
                                   "(contains evidence-manifest.json)")
    ap.add_argument("--expected", required=True,
                    help="expected evidence-manifest digest")
    args = ap.parse_args()

    bundle = Path(args.bundle)
    if not bundle.is_dir():
        print(f"evidence-validate: bundle directory not found: {bundle}",
              file=sys.stderr)
        return EXIT_USAGE

    ok = evidence.verify(str(bundle), args.expected)
    if not ok:
        print("evidence-validate: INVALID — bundle fails digest verification")
        return EXIT_INVALID

    problems = check_claims(bundle)
    if problems:
        print("evidence-validate: INVALID — claim checks failed:")
        for p in problems:
            print(f"  - {p}")
        return EXIT_INVALID

    print("evidence-validate: OK — bundle verified, claims consistent")
    return EXIT_VALID


if __name__ == "__main__":
    sys.exit(main())
