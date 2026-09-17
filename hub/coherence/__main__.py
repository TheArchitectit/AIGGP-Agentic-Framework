# // spec: coh-dec-01, coh-dec-04
"""CLI entry point: python -m hub.coherence --request request.json

Time and stage come only from the evaluation context, never the host clock.
Exit codes per the frozen decision/exit matrix. Stdlib-only.
"""
import argparse
import json
import sys
from pathlib import Path

from . import context, evidence, evaluate, manifest, package, plan, result


def _emit(path: str, payload: bytes) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(payload)


def run(request_path: str) -> int:
    req = json.loads(Path(request_path).read_text())
    out_dir = req["outputs"]

    identities = {}
    # Validate inputs in order; each failure maps to its exit class.
    try:
        subject = manifest.build(req["subject"]["root"],
                                 req["subject"].get("kind", "source-tree"))
        identities["subject_digest"] = subject["subject_digest"]
    except manifest.SubjectError as e:
        env = result.error_envelope("invalid-input", str(e), "subject-resolution", identities)
        _emit(f"{out_dir}/result.json", result.to_canonical(env))
        return result.EXIT_INVALID_INPUT

    try:
        pkg = package.resolve(req["openspec"]["root"])
        identities["openspec_digest"] = pkg["package_digest"]
    except package.PackageError as e:
        env = result.error_envelope("invalid-input", str(e), "package-resolution", identities)
        _emit(f"{out_dir}/result.json", result.to_canonical(env))
        return result.EXIT_INVALID_INPUT

    try:
        ctx = context.load(req["context"]["root"])
        identities["context_digest"] = ctx["context_digest"]
    except context.ContextError as e:
        env = result.error_envelope("policy-resolution", str(e), "context", identities)
        _emit(f"{out_dir}/result.json", result.to_canonical(env))
        return result.EXIT_POLICY

    identities["policy_digest"] = req["policy"]["expected_digest"]
    identities["evaluator_image_digest"] = "sha256:" + "0" * 64  # stdlib slice placeholder
    identities["platform"] = {
        "index_digest": None, "manifest_digest": "sha256:" + "0" * 64,
        "profile": ctx.get("execution_profile", "linux-amd64-v1"),
    }

    assertions = _load_assertions(req["openspec"]["root"])
    central_required = []  # from policy bundle in a later sprint
    try:
        planned = plan.plan(assertions, central_required)
    except plan.PlanError as e:
        env = result.error_envelope("invalid-input", str(e), "planning", identities)
        _emit(f"{out_dir}/result.json", result.to_canonical(env))
        return result.EXIT_INVALID_INPUT

    eval_out = evaluate.run(planned, pkg, req["subject"]["root"])
    ledger, findings = eval_out["ledger"], eval_out["findings"]

    try:
        ev_digest = evidence.seal(findings, out_dir)
    except evidence.EvidenceError as e:
        env = result.error_envelope("evidence", str(e), "sealing", identities)
        _emit(f"{out_dir}/result.json", result.to_canonical(env))
        return result.EXIT_EVIDENCE

    res = result.build(ledger, findings, identities, ctx["stage"],
                       ctx.get("semantics", "fresh-promotion"), ev_digest)
    _emit(f"{out_dir}/result.json", result.to_canonical(res))
    _, code = result.decide(ledger, ctx["stage"])
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
