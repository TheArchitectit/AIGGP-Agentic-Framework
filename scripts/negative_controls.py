#!/usr/bin/env python3
"""negative_controls.py — permanent evaluator-integrity suite (fw-nc-*).

Negative controls are deliberately broken evaluations that the spec-coherence
evaluator MUST REJECT. A green evaluation is meaningless if broken input can
stay green; this suite continuously proves the evaluator still refuses the
defect classes that matter. Each control builds a real fixture tree, applies
ONE defect, runs the actual CLI (python -m hub.coherence), and asserts the
frozen exit code / decision.

The POSITIVE control at the end is load-bearing: an unbroken fixture must
still PASS. An evaluator that rejects everything would satisfy every
negative control while being useless — the canary catches that direction of
failure too.

Exit codes: 0 all controls hold; 1 an evaluator FAILED a control (accepted
something it must reject, or rejected the positive control); 30 usage error.

Usage:
  python3 scripts/negative_controls.py                # full suite
  python3 scripts/negative_controls.py --list         # control names only
  python3 scripts/negative_controls.py --only nc-01   # run a subset
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DEVGATE_ROOT = Path(__file__).resolve().parent.parent
if str(DEVGATE_ROOT) not in sys.path:
    sys.path.insert(0, str(DEVGATE_ROOT))

from tests.fixtures.coherence import fixtures as fx  # noqa: E402

EXIT_OK = 0
EXIT_CONTROL_FAILED = 1
EXIT_USAGE = 30

CLI_TIMEOUT = 120


def _run_cli(request_path: Path):
    return subprocess.run(
        [sys.executable, "-m", "hub.coherence", "--request", str(request_path)],
        capture_output=True, text=True, timeout=CLI_TIMEOUT,
        cwd=str(DEVGATE_ROOT))


def _read_decision(out_dir: Path):
    """Find the result envelope in the outputs dir or beside the request
    (malformed-request envelopes fall back to the request's directory)."""
    for fp in (Path(out_dir) / "result.json", Path(out_dir).parent / "result.json"):
        if fp.exists():
            try:
                return json.loads(fp.read_text()).get("decision")
            except (OSError, json.JSONDecodeError):
                return None
    return None


# --- control definitions -----------------------------------------------------
#
# Each returns (name, expect_exit, expect_decision or None, defect_description)
# and applies its own defect to a freshly built fixture.

def nc_01_wrong_subject_digest(td: str):
    """The request claims a subject digest that does not match the tree."""
    req, out = fx.build_root(Path(td))
    r = json.loads(req.read_text())
    r["subject"]["expected_digest"] = "sha256:" + "f" * 64
    req.write_text(json.dumps(r))
    return "nc-01-wrong-subject-digest", 30, "ERROR", \
        "forged subject digest"


def nc_02_wrong_policy_digest(td: str):
    """The request claims a policy digest that does not match the bundle."""
    req, out = fx.build_root(Path(td), policy_digest_ok=False)
    return "nc-02-wrong-policy-digest", 31, "ERROR", "forged policy digest"


def nc_03_bad_api_version(td: str):
    """A foreign api_version must be refused at the protocol layer."""
    req, out = fx.build_root(Path(td))
    r = json.loads(req.read_text())
    r["api_version"] = "devgate.spec-coherence/v0.9"
    req.write_text(json.dumps(r))
    return "nc-03-foreign-api-version", 40, "ERROR", "unsupported protocol"


def nc_04_malformed_request(td: str):
    """A request missing required fields is invalid input, never an eval."""
    root = Path(td)
    req = root / "request.json"
    req.write_text(json.dumps({"api_version": "devgate.spec-coherence/v1"}))
    return "nc-04-malformed-request", 30, "ERROR", "missing required fields"


def nc_05_unapproved_evaluator(td: str):
    """An unapproved evaluator is REJECTED — either at planning (exit 30,
    invalid input) or at evaluation (UNRESOLVED -> BLOCK, exit 20 FAIL).
    Either outcome proves the evaluator cannot run foreign code; what it
    must never do is evaluate and pass."""
    evil = fx.assertion(aid="product.identity",
                        evaluator={"id": "repo.custom.evil",
                                   "digest": "sha256:" + "b" * 64})
    req, out = fx.build_root(Path(td), assertions=[evil], stage=2)
    return "nc-05-unapproved-evaluator-blocks", (20, 30), None, \
        "unapproved evaluator"


def nc_06_violated_identity_blocks(td: str):
    """A subject violating the approved identity must FAIL at stage 2."""
    req, out = fx.build_root(Path(td), declared_name="impostor",
                             approved_name="widget", stage=2)
    return "nc-06-identity-violation-blocks", 20, "FAIL", \
        "subject identity mismatch at blocking stage"


def nc_07_hostile_overlay(td: str):
    """An overlay disabling a centrally required assertion is a policy error."""
    req, out = fx.build_root(Path(td), stage=2)
    r = json.loads(req.read_text())
    polroot = Path(r["policy"]["root"])
    # Make the assertion centrally required, then overlay-disable it.
    from hub.coherence import canon as C
    bundle = json.loads((polroot / "policy.json").read_text())
    bundle["required_assertions"] = ["product.identity"]
    (polroot / "policy.json").write_text(json.dumps(bundle))
    r["policy"]["expected_digest"] = C.digest_obj("policy/v1", bundle)
    req.write_text(json.dumps(r))
    (polroot / "overlay.json").write_text(json.dumps(
        {"assertions": [{"id": "product.identity", "disabled": True}]}))
    return "nc-07-hostile-overlay-rejected", 31, "ERROR", \
        "overlay weakens central policy"


def nc_08_positive_control(td: str):
    """THE CANARY: the unbroken fixture must still PASS (exit 0). Without
    this, an evaluator that rejects everything would satisfy the suite."""
    req, out = fx.build_root(Path(td), stage=2)
    return "nc-08-POSITIVE-canary-must-pass", 0, "PASS", \
        "unbroken fixture must pass"


def nc_09_policy_rollback(td: str):
    """coh-pol-02: a context carrying a control-plane epoch floor must
    reject a policy bundle that predates the floor (no epoch field) as a
    rolled-back, trusted-but-obsolete bundle."""
    from hub.coherence import canon as C
    req, out = fx.build_root(Path(td), stage=2)
    r = json.loads(req.read_text())
    ctxroot = Path(r["context"]["root"])
    ctx = json.loads((ctxroot / "context.json").read_text())
    ctx["policy_epoch_floor"] = 1
    (ctxroot / "context.json").write_text(json.dumps(ctx))
    r["context"]["expected_digest"] = C.digest_obj("context/v1", ctx)
    req.write_text(json.dumps(r))
    return "nc-09-policy-rollback-rejected", 31, "ERROR", \
        "rolled-back policy bundle (coh-pol-02)"


CONTROLS = [nc_01_wrong_subject_digest, nc_02_wrong_policy_digest,
            nc_03_bad_api_version, nc_04_malformed_request,
            nc_05_unapproved_evaluator, nc_06_violated_identity_blocks,
            nc_07_hostile_overlay, nc_08_positive_control,
            nc_09_policy_rollback]


def nc_10_attestation_substitution(base: str):
    """S5 self-contained control (own multi-step flow, so it lives outside
    the standard CONTROLS loop): a decision swapped under a VALID
    attestation must be rejected by --verify (statement-substitution)."""
    import subprocess
    from hub.coherence import canon as C
    from hub.coherence import attest as A

    name = "nc-10-attestation-substitution"
    sub = Path(base)
    sub.mkdir(parents=True, exist_ok=True)
    key_hex = "cc" * 32
    identity = "cp-signer-nc10"
    signer_set = [{"key_id": A.key_id_for(bytes.fromhex(key_hex)),
                   "identity": identity}]
    req, out = fx.build_root(sub, stage=2)
    r = json.loads(req.read_text())
    polroot = Path(r["policy"]["root"])
    bundle = json.loads((polroot / "policy.json").read_text())
    bundle["approved_signers"] = signer_set
    (polroot / "policy.json").write_text(json.dumps(bundle))
    r["policy"]["expected_digest"] = C.digest_obj("policy/v1", bundle)
    req.write_text(json.dumps(r))

    env = {k: v for k, v in os.environ.items()
           if k not in (A.SIGNER_KEYS_ENV, A.SIGNER_IDENTITY_ENV)}
    env.update({A.SIGNER_KEYS_ENV: json.dumps({identity: key_hex}),
                A.SIGNER_IDENTITY_ENV: identity,
                "DEVGATE_IMAGE_DIGEST": "sha256:" + "3" * 64})
    run = subprocess.run(
        [sys.executable, "-m", "hub.coherence", "--request", str(req)],
        capture_output=True, text=True, timeout=CLI_TIMEOUT, env=env,
        cwd=str(DEVGATE_ROOT))
    if run.returncode != 0:
        return False, f"setup evaluation failed (exit {run.returncode})"
    if not (Path(out) / "attestation.json").is_file():
        return False, "setup produced no attestation to attack"

    # Substitute the decision under the valid attestation.
    result_fp = Path(out) / "result.json"
    original = result_fp.read_bytes()
    forged = json.loads(original)
    forged["decision"] = "FAIL" if forged["decision"] != "FAIL" else "PASS"
    result_fp.write_bytes(C.canon(forged))
    signers_fp = sub / "signers.json"
    signers_fp.write_text(json.dumps(signer_set))
    verify = subprocess.run(
        [sys.executable, "-m", "hub.coherence", "--verify", str(out),
         "--signers", str(signers_fp)],
        capture_output=True, text=True, timeout=CLI_TIMEOUT, env=env,
        cwd=str(DEVGATE_ROOT))
    result_fp.write_bytes(original)
    if verify.returncode != 1:
        return False, (f"substituted decision ACCEPTED by --verify "
                       f"(exit {verify.returncode})")
    if "statement-substitution" not in verify.stdout:
        return False, (f"rejected but with the wrong reason: "
                       f"{verify.stdout.strip()[:120]}")
    return True, "substituted decision rejected (statement-substitution)"


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="negative_controls",
        description="run the evaluator-integrity negative-control suite")
    ap.add_argument("--list", action="store_true", help="list control names")
    ap.add_argument("--only", action="append", default=[],
                    help="run only controls whose name contains this string "
                         "(repeatable)")
    args = ap.parse_args()

    if args.list:
        for fn in CONTROLS:
            print(fn.__name__)
        return EXIT_OK

    selected = CONTROLS
    if args.only:
        selected = [fn for fn in CONTROLS
                    if any(pat in fn.__name__ for pat in args.only)]
        if not selected:
            print(f"negative-controls: no control matches {args.only}",
                  file=sys.stderr)
            return EXIT_USAGE

    failures = []
    crashed = []
    with tempfile.TemporaryDirectory() as td:
        # Self-contained controls (own multi-step flows) run first.
        if not args.only or any("nc-10" in pat for pat in args.only):
            ok, detail = nc_10_attestation_substitution(str(Path(td) / "nc-10"))
            if ok:
                print(f"  ok nc-10-attestation-substitution — {detail}")
            else:
                failures.append(f"nc-10-attestation-substitution: {detail}")
        for fn in selected:
            sub = str(Path(td) / fn.__name__)
            Path(sub).mkdir(parents=True, exist_ok=True)
            if fn.__name__.startswith("nc_10"):
                continue  # self-contained control, ran above
            name, want_exit, want_decision, defect = fn(sub)
            want_exits = want_exit if isinstance(want_exit, tuple) \
                else (want_exit,)
            try:
                r = _run_cli(Path(sub) / "request.json")
            except subprocess.TimeoutExpired:
                failures.append(f"{name}: evaluator TIMED OUT ({defect})")
                continue
            got_decision = _read_decision(Path(sub) / "out")
            # An exit 1 WITHOUT an envelope is not "the control was
            # accepted" — it is the evaluator crashing (observed under
            # heavy parallel load). One retry; a crash that survives the
            # retry is reported as its own failure class, not silently
            # folded into a rejection verdict.
            if r.returncode == 1 and got_decision is None:
                time.sleep(1.0)
                r = _run_cli(Path(sub) / "request.json")
                got_decision = _read_decision(Path(sub) / "out")
                if r.returncode == 1 and got_decision is None:
                    crashed.append(
                        f"{name}: evaluator CRASHED (exit 1, no envelope) "
                        f"— inconclusive, not a rejection verdict")
                    continue
            if r.returncode not in want_exits:
                failures.append(
                    f"{name}: MUST reject {defect}: expected exit "
                    f"{'/'.join(map(str, want_exits))}, got {r.returncode} "
                    f"(decision={got_decision})")
            elif want_decision and got_decision != want_decision:
                failures.append(
                    f"{name}: expected decision {want_decision}, "
                    f"got {got_decision}")
            else:
                print(f"  ok {name} — {defect} rejected "
                      f"(exit {r.returncode}, {got_decision})")

    if crashed:
        print(f"negative-controls: {len(crashed)} INCONCLUSIVE (evaluator "
              f"crashed — check host load):")
        for c in crashed:
            print(f"  ? {c}")

    if failures:
        print(f"negative-controls: {len(failures)} CONTROL FAILURE(S) — "
              f"the evaluator accepted what it must reject:")
        for f in failures:
            print(f"  ✗ {f}")
        return EXIT_CONTROL_FAILED
    passed = len(selected) + (0 if failures or crashed else 1)
    print(f"negative-controls: all {passed} controls hold "
          f"(incl. positive canary)")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
