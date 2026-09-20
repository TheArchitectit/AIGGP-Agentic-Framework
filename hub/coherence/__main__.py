# // spec: coh-dec-01, coh-dec-02, coh-dec-04, coh-pol-02, coh-pkg-02
"""CLI entry point: python -m hub.coherence --request request.json

Time and stage come only from the evaluation context, never the host clock.
Exit codes per the frozen decision/exit matrix. Stdlib-only.

Identity fields the slice cannot compute (evaluator image digest, platform
manifest digest) are carried as explicit nulls, never fabricated (coh-dec-02).

The request is validated against request.schema.json at entry (S3): a
malformed or wrong-typed request yields the documented invalid-input envelope,
never a raw traceback — the durable fix behind the r3-indep crash-vector
family.
"""
import argparse
import json
import os
import sys
from functools import lru_cache
from pathlib import Path

from . import (adoption, attest, canon, container_exec, context, evaluate,
               evidence, manifest, package, plan, policy, profiles, result,
               schemacheck, verification)

# Runtime contracts live with the service package (fix-coherence-container-
# contract): resolving relative to THIS file keeps host-side and in-container
# runs identical — the image carries hub/ wholesale, so the schemas ride in
# it. They must never resolve through repository or change-package layout:
# archiving a change package once moved these files and broke every load.
SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
PROFILE_REGISTRY = Path(__file__).resolve().parent.parent.parent / \
    "container/execution-profiles.json"


@lru_cache(maxsize=8)
def _schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text())


def _fail(out_dir: str, error_class: str, reason: str, stage: str,
          identities: dict) -> int:
    env = result.error_envelope(error_class, reason, stage, identities)
    result.emit_with_fallback(out_dir, result.to_canonical(env))
    _, code = result.decide([], 0, error_class=error_class)
    return code


def _require(obj: dict, key: str, where: str):
    """Fetch a required key with a message that names it (round-4, low):
    a raw KeyError surfaced as "'root'" in the envelope reason."""
    try:
        return obj[key]
    except KeyError:
        raise KeyError(f"missing required field: {where}.{key}") from None


SUPPORTED_API = "devgate.spec-coherence/v1"


REQUIRED_REQUEST_FIELDS = ("api_version", "subject", "openspec", "policy",
                           "context", "semantics", "outputs")


def _check_expected(claimed, actual: str, label: str) -> None:
    """Verify a caller-supplied expected digest against computed content.

    Round-2 audit finding 6a: these fields were previously carried but never
    checked. Round-3-independent item 5: a null/absent/empty claim must not
    silently skip verification — `request.schema.json`'s inputRef makes
    `expected_digest` required whenever a reference object is present, so a
    missing claim is invalid input, not a bypass. (A wholly absent subject/
    openspec/policy/context object is a separate missing-required-field error
    caught at request parse time.)
    """
    if not isinstance(claimed, str) or not claimed.strip():
        raise ValueError(
            f"{label}.expected_digest is required and must be a non-empty "
            f"string; verification cannot be skipped")
    if claimed != actual:
        raise ValueError(
            f"{label} digest mismatch: request expected {claimed}, "
            f"computed {actual}")


def _safe_out_dir(req: dict, request_path: str) -> str:
    """Best-effort envelope location before the request is schema-validated."""
    raw = req.get("outputs")
    if isinstance(raw, str) and raw.strip() and "\x00" not in raw:
        return raw.strip()
    return str(Path(request_path).resolve().parent)


def run(request_path: str) -> int:
    out_dir = str(Path(request_path).resolve().parent)
    try:
        req = json.loads(Path(request_path).read_text())
        if not isinstance(req, dict):
            raise ValueError("request must be a JSON object")
        # Protocol guard before deep validation (coh-dec-04, exit 40): a
        # foreign api_version must not be judged by this version's schema.
        if req.get("api_version") != SUPPORTED_API:
            return _fail(_safe_out_dir(req, request_path), "protocol",
                         f"unsupported api_version {req.get('api_version')!r}; "
                         f"supported: {SUPPORTED_API}", "invocation", {})
        # Validate against the frozen request contract BEFORE any field is
        # touched (S3 runtime-schema item): structure, required fields,
        # inputRef shapes, semantics enum, outputs type. Replaces the piecemeal
        # guards the earlier audit rounds patched in one by one. NUL paths
        # would raise inside mkdir (not OSError), so they are rejected here too.
        errors = schemacheck.validate(req, _schema("request.schema.json"))
        if errors:
            raise ValueError("invalid request: " + "; ".join(errors[:5]))
        raw_out = req.get("outputs")
        if isinstance(raw_out, str) and "\x00" in raw_out:
            raise ValueError("outputs contains an embedded NUL character")
        # Empty/whitespace outputs must NOT mean "caller's cwd" — fall back to
        # the request's own directory.
        out_dir = (raw_out or "").strip() or out_dir
    except (OSError, json.JSONDecodeError, ValueError,
            schemacheck.SchemaError, RecursionError) as e:
        # Malformed request must yield an envelope, never a raw traceback
        # (round-2 audit finding 6b), written beside the request file rather
        # than polluting the working directory. RecursionError included
        # (fw-rt-01): the stdlib parser raises it on pathologically deep
        # nesting, and it is a RuntimeError — outside the ValueError family.
        return _fail(out_dir, "invalid-input", f"malformed request: {e}",
                     "invocation", {})

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
        # Captured-fact content is digest-verified at load (coh-rt-03):
        # replay reads the bound content, never a live fetch.
        facts = context.load_captured_facts(req["context"]["root"], ctx)
    except (context.ContextError, ValueError, KeyError, TypeError) as e:
        return _fail(out_dir, "policy-resolution", str(e), "context", identities)

    # Policy identity is verified against real content; the caller's claimed
    # digest is never trusted as authority (coh-pol-02). KeyError/TypeError
    # included (r3-indep item 3): a policy block without "root" is a policy
    # resolution error, not a crash — request schema validation at the
    # adapter is the durable fix, this is the slice guard.
    try:
        pol = policy.resolve(_require(req["policy"], "root", "policy"),
                             _require(req["policy"], "expected_digest", "policy"))
        identities["policy_digest"] = pol["policy_digest"]
        # Anti-rollback (coh-pol-02, S6): the signed context carries the
        # control-plane epoch floor; a bundle below it is a rolled-back,
        # trusted-but-obsolete bundle and is rejected here, before it can
        # influence any decision.
        attest.check_anti_rollback(pol.get("min_bundle_epoch"),
                                   ctx.get("policy_epoch_floor"))
    except (policy.PolicyError, attest.AttestationError, KeyError,
            TypeError) as e:
        return _fail(out_dir, "policy-resolution", str(e), "policy-resolution",
                     identities)

    # Execution identity (coh-id-04, S4/S6): the host launcher injects the
    # digest-pinned ref it executed (DEVGATE_IMAGE_DIGEST); the runtime
    # self-identifies instead of recording a fabricated-or-null digest.
    # Absence remains an explicit null (coh-dec-02) — known-unknown, never
    # invented. A malformed injection is a hard protocol error.
    try:
        identities["evaluator_image_digest"] = \
            profiles.execution_identity()
    except profiles.ProfileRegistryError as e:
        return _fail(out_dir, "protocol", str(e), "invocation", identities)
    identities["platform"] = {
        "index_digest": None,
        "manifest_digest": None,
        "profile": ctx.get("execution_profile", "linux-amd64-v1"),
    }

    try:
        assertions = _load_assertions(req["openspec"]["root"])
    except (OSError, json.JSONDecodeError, RecursionError) as e:
        # RecursionError (fw-rt-01): an assertion file with pathological
        # nesting is invalid input, not a crash.
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
        eval_out = evaluate.run(planned, pkg, req["subject"]["root"],
                                captured_facts=facts)
    except evaluate.EvaluatorError as e:
        return _fail(out_dir, "execution", str(e), "evaluation", identities)
    ledger, findings = eval_out["ledger"], eval_out["findings"]

    # Adoption ladder: baseline ratchet + scoped exceptions (coh-pol-04..06).
    # JSONDecodeError/KeyError/TypeError included (r3-indep item 4): a
    # malformed baseline/exceptions file is exit 31, never a traceback.
    try:
        baseline, exceptions = policy.load_adoption_sets(req["policy"]["root"])
        # Sets must hash to the digests bound in the signed context
        # (coh-ctx-01): a policy content-swap after issuance is detected here.
        context.verify_bound_sets(ctx, baseline, exceptions)
        adoption_out = adoption.evaluate(
            ledger, findings, planned, baseline, exceptions,
            ctx["stage"], ctx["evaluation_time"])
    except (policy.PolicyError, json.JSONDecodeError, KeyError, TypeError,
            ValueError) as e:
        return _fail(out_dir, "policy-resolution", str(e), "adoption", identities)
    ledger, findings = adoption_out["ledger"], adoption_out["findings"]

    # coh-ctx-03 replay labeling lives IN the payload: the canonical result
    # carries `semantics` (required by result.schema.json), so a replayed
    # decision is structurally distinguishable and non-promotion-authorizing;
    # consumers and report.summarize derive the flag from it. Nothing to do
    # here — and nothing else may silently "authorize" on a replay.

    try:
        ev_digest = evidence.seal(findings, out_dir)
    except evidence.EvidenceError as e:
        return _fail(out_dir, "evidence", str(e), "sealing", identities)

    res = result.build(ledger, findings, identities, ctx["stage"],
                       ctx.get("semantics", "fresh-promotion"), ev_digest,
                       blocked=adoption_out["blocked"])
    # Success path goes through the fallback too (r3-indep item 2): if the
    # decision was computed but result.json cannot be written (occupied by a
    # directory, dir flipped read-only after seal), the payload lands beside
    # the request with an stderr announcement — never exit 1 + traceback.
    payload = result.to_canonical(res)
    final_dir = result.emit_with_fallback(out_dir, payload)
    _, code = result.decide(ledger, ctx["stage"], blocked=adoption_out["blocked"])

    # Detached attestation (coh-ev-01, coh-ev-05, S5): produced AFTER the
    # decision and evidence are sealed — the acyclic sealing order. The
    # decision payload contains no attestation material; the attestation
    # binds the exact emitted bytes. Unconfigured signing is honest absence:
    # no attestation file, unchanged exit code. CONFIGURED-but-unauthorized
    # (identity without a key, or not in the policy's approved signer set,
    # or revoked) is a policy error — an operator who turned signing on must
    # never get silent non-signing on a promotion-authorizing run.
    if attest._keys():
        identity = attest.signer_identity()
        try:
            if not identity:
                raise attest.AttestationError(
                    "signer keys configured but HUB_COHERENCE_SIGNER_IDENTITY "
                    "is unset; refusing to skip attestation silently")
            approved = {
                e.get("identity"): e
                for e in (pol.get("approved_signers") or [])
                if isinstance(e, dict)}
            if identity not in approved:
                raise attest.AttestationError(
                    f"signer identity {identity!r} is not in the policy's "
                    f"approved signer set")
            if approved[identity].get("revoked"):
                raise attest.AttestationError(
                    f"signer identity {identity!r} is revoked")
            att = attest.attest(payload, {
                "subject_digest": identities["subject_digest"],
                "openspec_digest": identities["openspec_digest"],
                "policy_digest": identities["policy_digest"],
                "context_digest": identities["context_digest"],
                "evaluator_image_digest": identities["evaluator_image_digest"],
                "evidence_manifest_digest": ev_digest,
            }, identity, issued_at=ctx.get("evaluation_time"))
            result.emit(str(Path(final_dir) / "attestation.json"),
                        canon.canon(att))
        except attest.AttestationError as e:
            return _fail(out_dir, "policy-resolution", str(e),
                         "attestation", identities)

    # Decision claim (fw-* verification semantics): the pipeline records
    # what it OBSERVED, bound to every input digest — and deliberately stops
    # at OBSERVED. A producer cannot certify its own output (the claim
    # lifecycle forbids self-issued VERIFIED); a consumer raises the claim
    # via independent re-verification (scripts/evidence-validate.py).
    claim = verification.new_claim(
        f"coherence-decision:{identities['subject_digest'][:23]}",
        f"spec-coherence decision for subject "
        f"{identities['subject_digest']}",
        subject_digest=identities["subject_digest"], actor="devgate-coherence")
    for role, digest in (
            ("subject", identities["subject_digest"]),
            ("openspec", identities["openspec_digest"]),
            ("policy", identities["policy_digest"]),
            ("context", identities["context_digest"]),
            ("evidence-manifest", ev_digest),
            ("decision", canon.digest_bytes("decision/v1", payload))):
        verification.bind(claim, role, digest)
    for state, reason in (
            (verification.ATTEMPTED, "request accepted, identities computed"),
            (verification.EXECUTED, "assertions executed"),
            (verification.COMPLETED, "decision computed"),
            (verification.TESTED, "assertion ledger complete"),
            (verification.OBSERVED,
             f"decision {res['decision']} sealed with evidence")):
        verification.transition(claim, state, reason=reason)
    verification.attach_evidence(claim, "evidence-manifest.json")
    claim_path = Path(final_dir) / "decision.claim.json"
    try:
        result.emit(str(claim_path), canon.canon(claim))
        result.emit(str(claim_path) + ".digest",
                    verification.digest_claim(claim).encode("utf-8"))
    except OSError:
        # The decision itself is already sealed; a claim-write failure must
        # not corrupt or mask it — surface loudly on stderr.
        print("warning: decision claim could not be written; the sealed "
              "decision is unaffected", file=sys.stderr)
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


def _verify_outcome(args) -> int:
    """Offline attestation verification (S5): check a sealed output
    directory's attestation.json against its result.json and an approved
    signer set. Exit 0 verified; 1 rejected (with the stable reason);
    30 usage/missing-input error."""
    out_dir = Path(args.verify)
    result_fp = out_dir / "result.json"
    att_fp = out_dir / "attestation.json"
    missing = [str(p) for p in (result_fp, att_fp) if not p.is_file()]
    if missing:
        print(f"hub.coherence --verify: missing input(s): "
              f"{', '.join(missing)}", file=sys.stderr)
        return EXIT_USAGE
    if not args.signers:
        print("hub.coherence --verify: --signers PATH (approved signer set) "
              "is required; verification without a signer set would be a "
              "rubber stamp", file=sys.stderr)
        return EXIT_USAGE
    try:
        result_payload = result_fp.read_bytes()
        attestation = json.loads(att_fp.read_text())
        signer_set = json.loads(Path(args.signers).read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"hub.coherence --verify: cannot read inputs: {e}",
              file=sys.stderr)
        return EXIT_USAGE

    # The decision's own claimed identities come from the result payload;
    # the attestation must bind exactly these (substitution detection).
    try:
        decided = json.loads(result_payload)
    except json.JSONDecodeError:
        print("hub.coherence --verify: result.json is not valid JSON",
              file=sys.stderr)
        return EXIT_USAGE
    identities = {
        "subject_digest": decided.get("subject_digest"),
        "openspec_digest": decided.get("openspec_digest"),
        "policy_digest": decided.get("policy_digest"),
        "context_digest": decided.get("context_digest"),
        "evaluator_image_digest": decided.get("evaluator_image_digest"),
        "evidence_manifest_digest": decided.get("evidence_manifest_digest"),
    }
    ok, reason = attest.verify(attestation, result_payload, identities,
                               signer_set,
                               reference_time=args.reference_time)
    if ok:
        print(f"attestation OK — signer {attestation['signer']['identity']} "
              f"({attestation['signer']['key_id']}) binds decision "
              f"{attestation['statement_digest']}")
        return 0
    print(f"attestation REJECTED: {reason}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(prog="hub.coherence")
    ap.add_argument("--request", help="Path to request JSON")
    ap.add_argument("--launch-config",
                    help="Host-side containerized execution: validate the "
                         "launch config against the execution-profile "
                         "registry, run the evaluation inside the pinned "
                         "image, and map launch failures to the exit-code "
                         "contract (coh-rt-05/07, coh-dec-04)")
    ap.add_argument("--verify", metavar="OUT_DIR",
                    help="offline attestation verification over a sealed "
                         "output directory (S5)")
    ap.add_argument("--signers", metavar="PATH",
                    help="approved signer set JSON for --verify")
    ap.add_argument("--reference-time",
                    help="reference time for signer validity windows "
                         "(coh-ctx-01: supply the context's "
                         "evaluation_time, never a host clock)")
    args = ap.parse_args()

    if args.verify:
        return _verify_outcome(args)

    if not args.request:
        ap.error("--request is required (or use --verify)")
    if args.launch_config:
        return container_exec.run_containerized(
            args.request, args.launch_config, str(PROFILE_REGISTRY))
    try:
        return run(args.request)
    except RecursionError:
        # fw-rt-01 backstop: ANY stage can raise RecursionError from the
        # stdlib JSON parser given pathologically deep nesting (manifest,
        # package, context, and policy files all parse repository-supplied
        # content). Hostile input gets the documented invalid-input envelope
        # beside the request, never a raw traceback with an undocumented
        # exit code.
        request_dir = str(Path(args.request).resolve().parent)
        return _fail(request_dir, "invalid-input",
                     "request inputs exceed supported nesting depth",
                     "invocation", {})


if __name__ == "__main__":
    sys.exit(main())