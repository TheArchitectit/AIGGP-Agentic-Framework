# // spec: coh-dec-01, coh-dec-02, coh-dec-04, coh-pol-02
"""CLI entry point: python -m hub.coherence --request request.json

Time and stage come only from the evaluation context, never the host clock.
Exit codes per the frozen decision/exit matrix. Stdlib-only.

Identity fields the slice cannot compute (evaluator image digest, platform
manifest digest) are carried as explicit nulls, never fabricated (coh-dec-02).
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

from . import adoption, context, evaluate, evidence, manifest, package, plan, policy, result


def _emit(path: str, payload: bytes) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(payload)


def _emit_with_fallback(out_dir: str, payload: bytes) -> str:
    """Write the envelope, falling back to a temp location.

    The error paths must never depend on the same directory that just failed:
    if `out_dir` is unwritable (a regular file, read-only, or nested under a
    file) writing there raises and the process dies with a traceback instead of
    returning the documented exit code (audit round 2, B1 — this made exit 33
    unreachable).
    """
    try:
        _emit(f"{out_dir}/result.json", payload)
        return out_dir
    except OSError:
        # The envelope must remain findable: announce the fallback location on
        # stderr so the operator holding exit 33 can locate the payload
        # (round-3 audit: an unfound envelope only half-meets the criterion).
        fallback = tempfile.mkdtemp(prefix="devgate-coherence-")
        _emit(f"{fallback}/result.json", payload)
        print(f"result written to fallback location: {fallback}/result.json",
              file=sys.stderr)
        return fallback


def _fail(out_dir: str, error_class: str, reason: str, stage: str,
          identities: dict) -> int:
    env = result.error_envelope(error_class, reason, stage, identities)
    _emit_with_fallback(out_dir, result.to_canonical(env))
    _, code = result.decide([], 0, error_class=error_class)
    return code


SUPPORTED_API = "devgate.spec-coherence/v1"


REQUIRED_REQUEST_FIELDS = ("api_version", "subject", "openspec", "policy",
                           "context", "semantics", "outputs")


def _check_expected(claimed: str, actual: str, label: str) -> None:
    """Verify a caller-supplied expected digest against computed content.

    Round-2 audit finding 6a: these fields were previously carried but never
    checked, so a wrong expected_digest silently produced PASS.
    """
    if claimed and claimed != actual:
        raise ValueError(
            f"{label} digest mismatch: request expected {claimed}, "
            f"computed {actual}")


def run(request_path: str) -> int:
    out_dir = "."
    try:
        req = json.loads(Path(request_path).read_text())
        if not isinstance(req, dict):
            raise ValueError("request must be a JSON object")
        # `outputs` must be a string with no embedded NUL. A non-string
        # (JSON array/number/object/bool) or NUL would otherwise crash the
        # error path itself (AttributeError on .strip, ValueError inside mkdir)
        # — exit 1 with a raw traceback instead of the documented envelope
        # (round-3 audit item 2; same class as finding 6b).
        raw_out = req.get("outputs")
        if raw_out is not None and not isinstance(raw_out, str):
            raise ValueError(
                f"outputs must be a string, got {type(raw_out).__name__}")
        if isinstance(raw_out, str) and "\x00" in raw_out:
            raise ValueError("outputs contains an embedded NUL character")
        # An absent, empty, or whitespace-only `outputs` must NOT silently mean
        # "the caller's cwd" — that writes results into whatever directory the
        # process happened to start in. Fall back to the request's own directory.
        out_dir = (raw_out or "").strip() or str(
            Path(request_path).resolve().parent)
        missing = [f for f in REQUIRED_REQUEST_FIELDS if f not in req]
        if missing:
            raise ValueError(f"request missing required field(s): {missing}")
    except (OSError, json.JSONDecodeError, ValueError) as e:
        # Malformed request must yield an envelope, never a raw traceback
        # (round-2 audit finding 6b). With no readable `outputs` field, write
        # beside the request file rather than polluting the working directory.
        if out_dir == ".":
            out_dir = str(Path(request_path).resolve().parent)
        return _fail(out_dir, "invalid-input", f"malformed request: {e}",
                     "invocation", {})

    # Protocol guard runs before any resolver (coh-dec-02, exit 40).
    if req.get("api_version") != SUPPORTED_API:
        return _fail(out_dir, "protocol",
                     f"unsupported api_version {req.get('api_version')!r}; "
                     f"supported: {SUPPORTED_API}", "invocation", {})

    identities = {}

    try:
        subject = manifest.build(req["subject"]["root"],
                                 req["subject"].get("kind", "source-tree"))
        identities["subject_digest"] = subject["subject_digest"]
        _check_expected(req["subject"].get("expected_digest"),
                        subject["subject_digest"], "subject")
    except (manifest.SubjectError, ValueError, KeyError, TypeError) as e:
        return _fail(out_dir, "invalid-input", str(e), "subject-resolution", identities)

    try:
        pkg = package.resolve(req["openspec"]["root"])
        identities["openspec_digest"] = pkg["package_digest"]
        _check_expected(req["openspec"].get("expected_digest"),
                        pkg["package_digest"], "openspec")
    except (package.PackageError, ValueError, KeyError, TypeError) as e:
        return _fail(out_dir, "invalid-input", str(e), "package-resolution", identities)

    try:
        ctx = context.load(req["context"]["root"])
        identities["context_digest"] = ctx["context_digest"]
        _check_expected(req["context"].get("expected_digest"),
                        ctx["context_digest"], "context")
    except (context.ContextError, ValueError, KeyError, TypeError) as e:
        return _fail(out_dir, "policy-resolution", str(e), "context", identities)

    # Policy identity is verified against real content; the caller's claimed
    # digest is never trusted as authority (coh-pol-02).
    try:
        pol = policy.resolve(req["policy"]["root"], req["policy"]["expected_digest"])
        identities["policy_digest"] = pol["policy_digest"]
    except policy.PolicyError as e:
        return _fail(out_dir, "policy-resolution", str(e), "policy-resolution", identities)

    # Slice cannot compute these; explicit nulls, never fabricated (coh-dec-02).
    identities["evaluator_image_digest"] = None
    identities["platform"] = {
        "index_digest": None,
        "manifest_digest": None,
        "profile": ctx.get("execution_profile", "linux-amd64-v1"),
    }

    try:
        assertions = _load_assertions(req["openspec"]["root"])
    except (OSError, json.JSONDecodeError) as e:
        return _fail(out_dir, "invalid-input", f"cannot load assertions: {e}",
                     "planning", identities)

    # Repository overlay may strengthen, never weaken (coh-pol-01).
    try:
        overlay = policy.load_overlay(req["policy"]["root"])
        if overlay:
            assertions = policy.apply_overlay(assertions, overlay, pol)
    except policy.OverlayError as e:
        return _fail(out_dir, "policy-resolution", str(e), "overlay", identities)
    except policy.PolicyError as e:
        return _fail(out_dir, "policy-resolution", str(e), "overlay", identities)

    try:
        planned = plan.plan(assertions, policy.central_required(pol),
                            requirements=pkg.get("normative_requirements"))
    except plan.PlanError as e:
        return _fail(out_dir, "invalid-input", str(e), "planning", identities)

    try:
        eval_out = evaluate.run(planned, pkg, req["subject"]["root"])
    except evaluate.EvaluatorError as e:
        return _fail(out_dir, "execution", str(e), "evaluation", identities)
    ledger, findings = eval_out["ledger"], eval_out["findings"]

    # Adoption ladder: baseline ratchet + scoped exceptions (coh-pol-04..06).
    try:
        baseline, exceptions = policy.load_adoption_sets(req["policy"]["root"])
        adoption_out = adoption.evaluate(
            ledger, findings, planned, baseline, exceptions,
            ctx["stage"], ctx["evaluation_time"])
    except policy.PolicyError as e:
        return _fail(out_dir, "policy-resolution", str(e), "adoption", identities)
    ledger, findings = adoption_out["ledger"], adoption_out["findings"]

    if not context.is_promotion_authorizing(ctx):
        # Replay reproduces a decision but never authorizes promotion
        # (coh-ctx-03); the decision itself is unchanged.
        pass

    try:
        ev_digest = evidence.seal(findings, out_dir)
    except evidence.EvidenceError as e:
        return _fail(out_dir, "evidence", str(e), "sealing", identities)

    res = result.build(ledger, findings, identities, ctx["stage"],
                       ctx.get("semantics", "fresh-promotion"), ev_digest,
                       blocked=adoption_out["blocked"])
    _emit(f"{out_dir}/result.json", result.to_canonical(res))
    _, code = result.decide(ledger, ctx["stage"], blocked=adoption_out["blocked"])
    return code


def _load_assertions(openspec_root: str) -> list:
    spec_dir = Path(openspec_root) / "specs"
    if not spec_dir.is_dir():
        return []
    out = []
    for f in sorted(spec_dir.glob("*.json")):
        data = json.loads(f.read_text())
        out.extend(data if isinstance(data, list) else [data])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(prog="hub.coherence")
    ap.add_argument("--request", required=True, help="Path to request JSON")
    args = ap.parse_args()
    return run(args.request)


if __name__ == "__main__":
    sys.exit(main())