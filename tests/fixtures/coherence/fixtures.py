# // spec: coh-pol-04, coh-pol-05, coh-pol-06, coh-eval-02, coh-dec-04, coh-ev-05
"""Fixture builders for the frozen S2 conformance suite (A-F).

All fixtures are SYNTHETIC and labeled as such (R9: no pilot provenance has
been captured, so nothing here may be represented as a real repository
baseline). Deterministic: fixed times, no network, no host clock.
"""
import json
import os
from pathlib import Path

from hub.coherence import canon

FIXED_TIME = "2026-09-17T00:00:00Z"
FIXED_ISSUED = "2026-09-17T00:00:00Z"

_HEX64 = "e" * 64


def digest_bytes(b: bytes) -> str:
    return canon.digest_bytes("file/v1", b)


def signer_set(key_hex: str, *, key_id="signer-1", identity="pilot-signer",
               as_of=None, valid_from=None, valid_until=None,
               revoked=False) -> dict:
    """Synthetic signer-set document (R9)."""
    as_of = as_of or FIXED_TIME
    valid_from = valid_from or "2026-01-01T00:00:00Z"
    valid_until = valid_until or "2027-01-01T00:00:00Z"
    signer = {
        "key_id": key_id, "identity": identity,
        "key": key_hex, "valid_from": valid_from,
        "valid_until": valid_until, "revoked": revoked,
    }
    if revoked:
        signer["revoked_at"] = as_of
    return {
        "api_version": "devgate.spec-coherence.signer-set/v1",
        "as_of": as_of,
        "signers": [signer],
    }


def cli_env() -> dict:
    """Environment dict for subprocess CLI calls requiring attestation.

    Signer vars only — the evaluator image digest is resolved from the
    execution-profile registry in local mode (no env var needed).
    """
    return {
        "HUB_COHERENCE_SIGNER_KEY": "a" * 64,
        "HUB_COHERENCE_SIGNER_KEY_ID": "signer-1",
        "HUB_COHERENCE_SIGNER_IDENTITY": "pilot-signer",
    }


def assertion(aid="product.identity", version=1, deps=None, evaluator=None,
              severity="high", params=None, subjects=None) -> dict:
    return {
        "id": aid, "version": version, "requirement_refs": ["prod-identity-01"],
        "owner": "portfolio-owner",
        "requirement": "docs and artifact metadata name the approved product",
        "subjects": subjects or [
            {"kind": "file", "path": "README.md"},
            {"kind": "artifact-metadata", "selector": "product.identity.name"},
        ],
        "evaluator": evaluator or {
            "id": "devgate.builtin.identity-consistency", "digest": "sha256:" + "a" * 64},
        "parameters": params if params is not None else {
            "approved_value_ref": "package:product.identity.name"},
        "severity": severity, "dependencies": deps or [],
        "finding_key": ["assertion_id", "subject_location", "violation_class"],
        "evidence": {"retention_days": 365},
    }


def build_root(tmp: Path, *, declared_name="widget", approved_name="widget",
               assertions=None, baseline=None, exceptions=None,
               stage=1, semantics="fresh-promotion", evaluation_time=FIXED_TIME,
               policy_digest_ok=True, subject_files=None,
               execution_profile="linux-amd64-v1", stages=None,
               advisory_escalation="__default__", repository=None,
               bundle_epoch=1, min_bundle_epoch=None,
               binding_expected_digest=None, grandfather_self_until=None,
               binding=True) -> tuple:
    """Build subject/package/policy/context/request under `tmp`.

    Returns (request_path, out_dir). Every input is real on disk so resolvers
    verify genuine content digests.
    """
    root = Path(tmp)
    # Subject
    subj = root / "subject"
    subj.mkdir(parents=True)
    for name, content in (subject_files or {"README.md": f"# product: {declared_name}\n"}).items():
        (subj / name).write_text(content)

    # Package
    pkg = root / "openspec"
    (pkg / "specs").mkdir(parents=True)
    assertions = assertions if assertions is not None else [assertion()]
    for i, a in enumerate(assertions):
        (pkg / "specs" / f"{a['id']}.json").write_text(json.dumps(a))
    inv = [{"path": str(f.relative_to(pkg)), "kind": "normative",
            "digest": digest_bytes(f.read_bytes())}
           for f in sorted((pkg / "specs").glob("*.json"))]
    (pkg / "package.json").write_text(json.dumps({
        "schema_version": "devgate.openspec.package/v1",
        "package_id": "com.test.widget", "package_version": "2026.09.17",
        "product": {"identity": {"name": approved_name}},
        "normative_inventory": inv, "imports": [],
    }))

    # Policy
    pol = root / "policy"
    pol.mkdir()
    bundle = {
        "api_version": "devgate.spec-coherence.policy/v1",
        "policy_version": "1", "bundle_epoch": bundle_epoch,
        "required_assertions": [], "approved_evaluators": [],
        "approved_signers": [],
        "stages": stages if stages is not None else {"max_advisory_age_days": 30},
    }
    # design.md round-16: declaring `stages` owes an escalation policy. The
    # sentinel keeps the default pair together while letting a test omit one
    # side deliberately (pass None) to exercise the refusal.
    if advisory_escalation == "__default__":
        bundle["advisory_escalation"] = {
            "on_expiry": "block",
            "renewal": {"requires": "central-approval",
                        "max_extension_days": 30}}
    elif advisory_escalation is not None:
        bundle["advisory_escalation"] = advisory_escalation
    if min_bundle_epoch is not None:
        bundle["min_bundle_epoch"] = min_bundle_epoch
    if baseline is not None:
        (pol / "baseline.json").write_text(json.dumps(baseline))
    if exceptions is not None:
        (pol / "exceptions.json").write_text(json.dumps(exceptions))
    (pol / "policy.json").write_text(json.dumps(bundle))
    real_policy_digest = canon.digest_obj("policy/v1", bundle)
    claimed = real_policy_digest if policy_digest_ok else "sha256:" + "f" * 64

    # Context — carries the anti-rollback binding (design.md round-15): the
    # written bundle is "current" unless the test overrides the expected
    # digest, optionally grandfathering the written bundle for a window.
    grandfathers = ([{"bundle_digest": real_policy_digest,
                      "valid_until": grandfather_self_until,
                      "reason": "fixture grandfather window"}]
                    if grandfather_self_until else [])
    policy_binding = None
    if binding:
        policy_binding = {
            "expected_digest": binding_expected_digest or real_policy_digest,
            "min_bundle_epoch": min_bundle_epoch if min_bundle_epoch is not None else 0,
            "grandfathers": grandfathers}
    ctx = root / "ctx"
    ctx.mkdir()
    ctx_dict = {
        "api_version": "devgate.spec-coherence.context/v1",
        "context_id": "fixture-ctx",
        "evaluation_time": evaluation_time, "stage": stage, "semantics": semantics,
        "baseline_set_digest": None, "exception_set_digest": None,
        "signer_set_digest": None, "capability_grants": [], "captured_facts": [],
        "execution_profile": execution_profile, "supported_runners": [execution_profile],
        "issuance": {"issued_at": FIXED_ISSUED, "issuer": "fixture-control-plane"},
    }
    if policy_binding is not None:
        ctx_dict["policy_binding"] = policy_binding
    (ctx / "context.json").write_text(json.dumps(ctx_dict))

    # Expected digests are REAL computed content digests, not placeholders:
    # the CLI verifies them (round-2 audit finding 6a), so a wrong value must
    # fail rather than silently PASS.
    from hub.coherence import manifest as _mf, package as _pk
    subject_digest = _mf.build(str(subj))["subject_digest"]
    openspec_digest = _pk.resolve(str(pkg))["package_digest"]
    # canon over the written dict — identical to context.load's digest, and
    # valid even for a deliberately binding-less (schema-invalid) fixture.
    context_digest = canon.digest_obj("context/v1", ctx_dict)

    out = root / "out"
    req = {
        "api_version": "devgate.spec-coherence/v1",
        "request_id": "fixture",
        "subject": {"kind": "source-tree", "root": str(subj),
                    "expected_digest": subject_digest},
        "openspec": {"root": str(pkg), "expected_digest": openspec_digest},
        "policy": {"root": str(pol), "expected_digest": claimed},
        "context": {"root": str(ctx), "expected_digest": context_digest},
        "semantics": semantics, "outputs": str(out),
    }
    # The repository record the advisory-age cap is measured against. It is
    # caller-supplied REQUEST state, not policy: the cap (a duration) is
    # central policy, how long THIS repo has been advisory is not.
    if repository is not None:
        req["repository"] = repository
    req_path = root / "request.json"
    req_path.write_text(json.dumps(req))
    return req_path, out


def baseline_entry(aid, version, location, vclass, status="open",
                   deadline="2026-12-31T00:00:00Z") -> dict:
    return {
        "fingerprint": {"assertion_id": aid, "assertion_version": version,
                        "subject_location": location, "violation_key": vclass},
        "severity": "high", "adopted_at": FIXED_TIME, "owner": "portfolio-owner",
        "status": status, "remediation_deadline": deadline,
        "remediation_ref": None,
    }


def exception_entry(aid, version, location, vclass, expires_at,
                    subject_ref="com.test.widget") -> dict:
    return {
        "exception_id": f"exc-{aid}-{vclass}",
        "subject_ref": subject_ref, "assertion_id": aid, "subject_path": location,
        "finding_fingerprint": {"assertion_id": aid, "assertion_version": version,
                                "subject_location": location, "violation_key": vclass},
        "owner": "portfolio-owner", "reason": "tracked migration",
        "approving_authority": "fleet-policy-owner",
        "created_at": FIXED_TIME, "expires_at": expires_at,
        "enforcement_treatment": "EXCEPTION-ADVISORY",
        "remediation_ref": "JIRA-123",
    }