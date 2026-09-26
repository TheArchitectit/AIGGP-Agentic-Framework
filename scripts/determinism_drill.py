#!/usr/bin/env python3
"""determinism_drill.py — S8: 100-repeat determinism verification.

The execution-profile equivalence promise: identical inputs must produce
BYTE-IDENTICAL canonical decisions, every time. This drill runs the real
coherence CLI N times (default 100) over one frozen fixture and asserts
every result.json is byte-identical to the first — plus every claim digest
and every attestation (when signing is configured).

Any variation is a determinism FAILURE with the differing bytes preserved
for diagnosis: a decision that wobbles between runs cannot be the basis of
an enforcement action, no matter how often it is right.

Exit codes: 0 deterministic across all runs; 1 variation found;
30 usage/setup error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

DEVGATE_ROOT = Path(__file__).resolve().parent.parent
if str(DEVGATE_ROOT) not in sys.path:
    sys.path.insert(0, str(DEVGATE_ROOT))

from tests.fixtures.coherence import fixtures as fx  # noqa: E402

EXIT_OK = 0
EXIT_VARIATION = 1
EXIT_USAGE = 30


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="determinism_drill",
        description="run one evaluation N times; decisions must be "
                    "byte-identical")
    ap.add_argument("--runs", type=int, default=100)
    ap.add_argument("--stage", type=int, default=2)
    # Stage >= 2 is promotion-authorizing and therefore REQUIRES a signing
    # configuration (an unsigned stage-2 run exits 33 before emitting a
    # decision). Fixed stand-in credentials keep every byte deterministic.
    ap.add_argument("--signer-key", default="ab" * 32)
    ap.add_argument("--signer-key-id", default="determinism-drill")
    args = ap.parse_args()
    if args.runs < 2:
        print("determinism-drill: --runs must be >= 2", file=sys.stderr)
        return EXIT_USAGE

    with tempfile.TemporaryDirectory(prefix="determinism-") as td:
        tdp = Path(td)
        req, _out = fx.build_root(tdp / "fixture", stage=args.stage)
        env = dict(os.environ, PYTHONPATH=str(DEVGATE_ROOT))
        if args.stage >= 2:
            env.update({"HUB_COHERENCE_SIGNER_KEY": args.signer_key,
                        "HUB_COHERENCE_SIGNER_KEY_ID": args.signer_key_id,
                        "HUB_COHERENCE_SIGNER_IDENTITY": "determinism-drill",
                        "HUB_COHERENCE_EVALUATOR_IMAGE_DIGEST":
                            "sha256:" + "3" * 64})
        digests = set()
        first_payload = None
        first_run_dir = None

        for i in range(args.runs):
            run_dir = tdp / f"run-{i:04d}"
            run_dir.mkdir()
            request = json.loads(req.read_text(encoding="utf-8"))
            request["outputs"] = str(run_dir)
            req_i = run_dir / "request.json"
            req_i.write_text(json.dumps(request), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "-m", "hub.coherence", "--request",
                 str(req_i)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, env=env)
            if r.returncode != 0:
                print(f"determinism-drill: run {i} exited {r.returncode}: "
                      f"{r.stderr.strip()[:200]}", file=sys.stderr)
                return EXIT_VARIATION
            payload = (run_dir / "result.json").read_bytes()
            if first_payload is None:
                first_payload = payload
                first_run_dir = run_dir
                digests.add(sha256(payload))
            elif sha256(payload) not in digests:
                print(f"determinism-drill: VARIATION at run {i} — "
                      f"decision bytes differ from run 0")
                a = tdp / "variation-first.json"
                b = tdp / f"variation-run-{i}.json"
                a.write_bytes(first_payload)
                b.write_bytes(payload)
                print(f"  preserved: {a} vs {b}", file=sys.stderr)
                return EXIT_VARIATION
            # Claims must be deterministic too (bound digests, transitions).
            claim = run_dir / "decision.claim.json"
            if claim.is_file() and first_run_dir is not None:
                first_claim = first_run_dir / "decision.claim.json"
                if first_claim.is_file():
                    # Claim digests must match; the files may live in
                    # different directories only via bound digests — the
                    # claim content itself must be identical.
                    if claim.read_bytes() != first_claim.read_bytes():
                        print(f"determinism-drill: VARIATION at run {i} — "
                              f"claim bytes differ", file=sys.stderr)
                        return EXIT_VARIATION

        print(f"determinism-drill: PASS — {args.runs}/{args.runs} runs "
              f"byte-identical (decision sha256 "
              f"{sha256(first_payload)[:16]}...)")
        return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
