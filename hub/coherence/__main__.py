# // spec: coh-dec-01, coh-dec-02, coh-dec-04, coh-pol-02, coh-pkg-02, coh-ev-01, coh-ev-05
"""CLI entry point: python -m hub.coherence --request request.json

Time and stage come only from the evaluation context, never the host clock.
Exit codes per the frozen decision/exit matrix. Stdlib-only.

Request is validated against request.schema.json at entry (S3): a malformed
request yields the invalid-input envelope, never a raw traceback (r3-indep).

From Stage 2 fresh-promotion onward, a signed detached attestation binds the
canonical decision to all input digests (coh-ev-01, coh-ev-05). The attestation
is a detached object; the canonical decision carries no attestation fields.
"""
import argparse
import json
import os
import re
import sys
from functools import lru_cache
from pathlib import Path

from . import (adoption, attest, container_exec, context, report,
               evaluate, evidence, manifest, package, plan, policy, profiles,
               result, schemacheck)

SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent / \
    "openspec/changes/devgate-spec-coherence-service/schemas"
PROFILE_REGISTRY = Path(__file__).resolve().parent.parent.parent / \
    "container/execution-profiles.json"
_EVALUATOR_IMAGE_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


@lru_cache(maxsize=8)
def _schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _fail(out_dir: str, error_class: str, reason: str, stage: str,
          identities: dict, ledger: list = None) -> int:
    env = result.error_envelope(error_class, reason, stage, identities,
                               assertion_results=ledger)
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
        req = json.loads(Path(request_path).read_text(encoding="utf-8"))
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
    except (OSError, json.JSONDecodeError, ValueError, schemacheck.SchemaError) as e:
        # Malformed request must yield an envelope, never a raw traceback
        # (round-2 audit finding 6b), written beside the request file rather
        # than polluting the working directory.
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
        # Anti-rollback (design.md round-15): the context's policy_binding is
        # the authority claim; a context without one is a substitution attempt
        # and resolve refuses (exit 31). Identity is still checked first.
        pol = policy.resolve(_require(req["policy"], "root", "policy"),
                             _require(req["policy"], "expected_digest", "policy"),
                             binding=ctx.get("policy_binding"),
                             evaluation_time=ctx["evaluation_time"])
        identities["policy_digest"] = pol["policy_digest"]
    except (policy.PolicyError, KeyError, TypeError) as e:
        return _fail(out_dir, "policy-resolution", str(e), "policy-resolution", identities)

    # Evaluator identity resolution order (coh-dec-02, coh-ev-05): the
    # container mode's env digest is authoritative (names the executed image);
    # otherwise the registry pin for the context's profile is the identity.
    ev_img = os.environ.get("HUB_COHERENCE_EVALUATOR_IMAGE_DIGEST")
    if ev_img is not None and not _EVALUATOR_IMAGE_RE.fullmatch(ev_img):
        return _fail(out_dir, "invalid-input",
                     "malformed HUB_COHERENCE_EVALUATOR_IMAGE_DIGEST",
                     "invocation", identities)
    profile_label = ctx.get("execution_profile", "linux-amd64-v1")
    try:
        identities.update(profiles.resolve_evaluator_identity(
            str(PROFILE_REGISTRY), profile_label, ev_img))
    except profiles.ProfileRegistryError as e:
        return _fail(out_dir, "invalid-input", str(e), "invocation", identities)

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
        eval_out = evaluate.run(planned, pkg, req["subject"]["root"],
                                captured_facts=facts, subject=subject)
    except evaluate.EvaluatorError as e:
        return _fail(out_dir, "execution", str(e), "evaluation", identities)
    ledger, findings = eval_out["ledger"], eval_out["findings"]
    if eval_out.get("error"):
        # Frozen matrix (decision-exit-matrix.md): an evaluator crash or a
        # dependency-blocked required assertion is ERROR-execution — it
        # dominates every FAIL-class condition in the same run (tie-break 2)
        # and is never converted to advisory, so the adoption ladder does
        # not run. The envelope still carries the full ledger so both
        # condition classes stay visible (coh-dec-01 scenario).
        return _fail(out_dir, "execution", eval_out["error"]["reason"],
                     "evaluation", identities, ledger=ledger)

    # Adoption ladder: baseline ratchet + scoped exceptions (coh-pol-04..06).
    # JSONDecodeError/KeyError/TypeError included (r3-indep item 4): a
    # malformed baseline/exceptions file is exit 31, never a traceback.
    try:
        baseline, exceptions = policy.load_adoption_sets(req["policy"]["root"])
        # coh-pol-03 (design.md round-16): the bundle's advisory-age cap is a
        # duration; advisory_escalation says what exceeding it does. Resolved
        # here from the CONTEXT's evaluation_time and the repository record
        # the caller supplied, so the age is read once, against the one
        # trusted clock, and the ladder receives a verdict rather than a date.
        record = req.get("repository") if isinstance(
            req.get("repository"), dict) else {}
        age = report.advisory_age(
            {**record, "stage": ctx["stage"]},
            (pol.get("stages") or {}).get("max_advisory_age_days", 0),
            ctx["evaluation_time"])
        escalation = policy.check_advisory_escalation(pol)
        advisory_expired = bool(age.get("expired")
                                and escalation.get("on_expiry") == "block")
        # Sets must hash to the digests bound in the signed context
        # (coh-ctx-01): a policy content-swap after issuance is detected here.
        context.verify_bound_sets(ctx, baseline, exceptions)
        # Explicit resolution (audit round-14): the caller passes the
        # bundle's core set, so a malformed stages.enforced_core_classes is a
        # policy refusal (exit 31) — the ladder default alone must never
        # paper over a bundle that attempted to define the core badly.
        adoption_out = adoption.evaluate(
            ledger, findings, planned, baseline, exceptions,
            ctx["stage"], ctx["evaluation_time"],
            core_classes=policy.enforced_core_classes(pol),
            # coh-pol-05: central policy's severity floor escalates adopted
            # debt. Passed explicitly so a bundle's floor is actually
            # consulted — a default standing in for it would be dead
            # configuration (the Cycle A m8 defect class).
            severity_floor=pol.get("assertion_severity_floor") or {},
            advisory_expired=advisory_expired)
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
        # coh-ev-02: each sealed object's retention_class comes from its
        # assertion's declared evidence.retention_days. A declared value is
        # passed straight through — even a negative or non-integer one, which
        # seal rejects fail-closed (the assertion schema's minimum:0 is not
        # enforced at runtime; see the round-9 plan-time carry-forward). An
        # assertion with no declared days is left unmapped so seal falls back
        # to the pre-existing "standard" for it rather than inventing a value.
        retention_days = {a["id"]: a["evidence"]["retention_days"]
                          for a in planned
                          if isinstance(a.get("evidence"), dict)
                          and "retention_days" in a["evidence"]}
        ev_digest = evidence.seal(findings, out_dir,
                                  retention_by_aid=retention_days)
    except evidence.EvidenceError as e:
        return _fail(out_dir, "evidence", str(e), "sealing", identities)

    res = result.build(ledger, findings, identities, ctx["stage"],
                       ctx.get("semantics", "fresh-promotion"), ev_digest,
                       blocked=adoption_out["blocked"])

    # Decision claim (fw-* verification semantics): record what this
    # pipeline OBSERVED, bound to every input digest — and stop at
    # OBSERVED. A producer cannot certify its own output (the claim
    # lifecycle forbids self-issued VERIFIED); consumers raise the claim
    # via scripts/evidence-validate.py. Emitted only AFTER seal_run
    # succeeds: an ERROR run (e.g. attestation failure at stage 2) must
    # not leave behind a claim describing a decision that was never
    # sealed. A claim-write failure is surfaced on stderr and never
    # corrupts or masks the sealed decision.
    try:
        code = attest.seal_run(out_dir, res, ledger, identities, ev_digest,
                               ctx, adoption_out["blocked"])
    except attest.AttestationError as e:
        return _fail(out_dir, "attestation", str(e),
                     "attestation", identities, ledger=ledger)
    _emit_decision_claim(out_dir, res, identities, ev_digest, ledger)
    return code


def _emit_decision_claim(out_dir: str, res: dict, identities: dict,
                         ev_digest: str, ledger: list) -> None:
    """Emit decision.claim.json (+ .digest sidecar) beside the decision.

    The claim walks the verification ladder REQUESTED->ATTEMPTED->EXECUTED
    ->COMPLETED->TESTED->OBSERVED with per-stage reasons, binds every
    identity digest plus the decision payload digest, and deliberately
    never reaches VERIFIED: reaching it requires an independent check the
    producer does not own.
    """
    from . import canon, verification
    try:
        payload = result.to_canonical(res)
        claim = verification.new_claim(
            f"coherence-decision:{(identities.get('subject_digest')
                                   or 'unknown')[:23]}",
            f"spec-coherence decision for subject "
            f"{identities.get('subject_digest')}",
            subject_digest=identities.get("subject_digest"),
            actor="devgate-coherence")
        for role, digest in (
                ("subject", identities.get("subject_digest")),
                ("openspec", identities.get("openspec_digest")),
                ("policy", identities.get("policy_digest")),
                ("context", identities.get("context_digest")),
                ("evidence-manifest", ev_digest),
                ("decision", canon.digest_bytes("decision/v1", payload))):
            if digest:
                verification.bind(claim, role, digest)
        for state, reason in (
                (verification.ATTEMPTED,
                 "request accepted, identities computed"),
                (verification.EXECUTED, "assertions executed"),
                (verification.COMPLETED, "decision computed"),
                (verification.TESTED,
                 f"assertion ledger complete ({len(ledger)} entries)"),
                (verification.OBSERVED,
                 f"decision {res.get('decision')} sealed with evidence")):
            verification.transition(claim, state, reason=reason)
        verification.attach_evidence(claim, "evidence-manifest.json")
        claim_path = Path(out_dir) / "decision.claim.json"
        result.emit(str(claim_path), canon.canon(claim))
        result.emit(str(claim_path) + ".digest",
                    verification.digest_claim(claim).encode("utf-8"))
    except (verification.VerificationError, OSError) as e:
        print(f"warning: decision claim could not be written; the sealed "
              f"decision is unaffected ({e})", file=sys.stderr)


def _load_assertions(openspec_root: str) -> list:
    spec_dir = Path(openspec_root) / "specs"
    if not spec_dir.is_dir():
        return []
    out = []
    for f in sorted(spec_dir.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        out.extend(data if isinstance(data, list) else [data])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(prog="hub.coherence")
    ap.add_argument("--request", help="Path to request JSON")
    ap.add_argument("--launch-config",
                    help="Host-side containerized execution: validate the "
                         "launch config against the execution-profile "
                         "registry, run the evaluation inside the pinned "
                         "image, and map launch failures to the exit-code "
                         "contract (coh-rt-05/07, coh-dec-04)")
    ap.add_argument("--verify-run",
                    help="Verify a completed run: path to the run directory "
                         "containing result.json, attestation.json, and "
                         "evidence-manifest.json")
    ap.add_argument("--signer-set",
                    help="Path to a signer-set document for verification "
                         "(required with --verify-run)")
    args = ap.parse_args()
    # --request is required for the evaluation path but NOT for the consumer
    # tools (--verify-run / --launch-config), which take their own arguments.
    # Declaring it argparse-required made both tools unreachable: argparse
    # rejected the invocation before dispatch (S5 audit).
    if args.verify_run is not None:
        if not args.signer_set:
            print("--signer-set is required with --verify-run",
                  file=sys.stderr)
            return 2
        return attest.verify_run_cli(args.verify_run, args.signer_set)
    if args.request is None:
        print("--request is required", file=sys.stderr)
        return 2
    if args.launch_config:
        return container_exec.run_containerized(
            args.request, args.launch_config, str(PROFILE_REGISTRY))
    return run(args.request)


if __name__ == "__main__":
    sys.exit(main())
