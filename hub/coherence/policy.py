# // spec: coh-pol-01, coh-pol-02, coh-pol-03
"""Policy resolution (slice minimum) and adoption-ladder inputs.

Slice scope: this verifies policy IDENTITY (content digest matches the expected
digest) and loads the baseline/exception sets. It does NOT yet establish
control-plane TRUST ROOTS or anti-rollback — that is S6 work (coh-pol-02,
coh-pol-01). Until then a resolved policy is identity-verified only, and callers
must not treat it as authoritative.
"""
import json
from pathlib import Path

from . import canon


class PolicyError(ValueError):
    """Policy resolution failure (exit-31 class)."""


def resolve(root: str, expected_digest: str) -> dict:
    """Resolve policy content and verify its digest against the expected value.

    Returns the policy bundle plus its computed digest. Raises PolicyError on
    missing content or digest mismatch.
    """
    root_p = Path(root).resolve()
    if not root_p.is_dir():
        raise PolicyError(f"policy root is not a directory: {root!r}")

    bundle_path = root_p / "policy.json"
    if not bundle_path.exists():
        raise PolicyError(f"missing policy bundle: {bundle_path}")

    try:
        bundle = json.loads(bundle_path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise PolicyError(f"cannot read policy bundle {bundle_path}: {e}") from e

    if bundle.get("api_version") != "devgate.spec-coherence.policy/v1":
        raise PolicyError(
            f"unsupported policy api_version: {bundle.get('api_version')!r}")

    # Identity check: the digest is computed from real content, never trusted
    # from the caller's claim.
    computed = canon.digest_obj("policy/v1", bundle)
    if computed != expected_digest:
        raise PolicyError(
            f"policy digest mismatch: expected {expected_digest}, computed {computed}")

    bundle["policy_digest"] = computed
    return bundle


def load_adoption_sets(root: str) -> tuple:
    """Load baseline entries and exceptions from the policy root, if present.

    Each set is shape-validated against its frozen schema (S3): a valid-JSON
    dict where a list is expected, entries with missing keys, or garbage
    timestamps are policy-resolution errors (exit 31) — never a crash deep in
    adoption.evaluate (round-4 carry-forward).
    """
    root_p = Path(root).resolve()
    baseline, exceptions = [], []
    b_path = root_p / "baseline.json"
    if b_path.exists():
        baseline = _load_json_set(b_path, "baseline set")
        errs = _check_entries(baseline, "baseline-entry.schema.json", "baseline")
        if errs:
            raise PolicyError("invalid baseline set: " + "; ".join(errs[:5]))
    e_path = root_p / "exceptions.json"
    if e_path.exists():
        exceptions = _load_json_set(e_path, "exception set")
        errs = _check_entries(exceptions, "exception.schema.json", "exception")
        if errs:
            raise PolicyError("invalid exception set: " + "; ".join(errs[:5]))
    return baseline, exceptions


def _load_json_set(path: Path, label: str) -> list:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        # r3-indep item 4: malformed sets are policy errors (exit 31), not raw
        # tracebacks — overlay.json was already handled cleanly; the asymmetry
        # was the bug.
        raise PolicyError(f"cannot read {label} {path}: {e}") from e
    if not isinstance(data, list):
        # Preserve the "cannot read {label} {path}:" prefix — a reason-text
        # pin asserts on it (a rename here would silently break the pin).
        raise PolicyError(
            f"cannot read {label} {path}: must be a JSON array, got "
            f"{type(data).__name__}")
    return data


def _check_entries(entries: list, schema_name: str, label: str) -> list:
    from . import schemacheck
    schema = schemacheck.load(schema_name)
    errs = []
    for i, entry in enumerate(entries):
        errs.extend(f"{label}[{i}]: {e}" for e in
                    schemacheck.validate(entry, schema))
    return errs


def central_required(bundle: dict) -> list:
    """Assertion IDs central policy requires (coh-pol-01)."""
    return list(bundle.get("required_assertions") or [])


# Severity ordering: a repository may raise severity, never lower it.
_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class OverlayError(ValueError):
    """Repository overlay attempted to weaken central policy (exit-31 class)."""


def apply_overlay(assertions: list, overlay: dict, central: dict) -> list:
    """Apply a repository overlay that may STRENGTHEN but never WEAKEN (coh-pol-01).

    Rejected, each with a stable reason:
      - selecting an evaluator not on the central approved list;
      - lowering an assertion's severity below the central floor;
      - disabling/removing a centrally required assertion;
      - granting network/secrets (granted only by control-plane policy).
    Additions and severity raises are permitted.
    """
    approved = {e["id"] for e in (central.get("approved_evaluators") or [])}
    floors = central.get("assertion_severity_floor") or {}
    required = set(central_required(central))
    by_id = {a["id"]: a for a in assertions}

    for changed in overlay.get("assertions", []):
        aid = changed.get("id")
        if changed.get("disabled"):
            if aid in required:
                raise OverlayError(
                    f"overlay disables centrally required assertion {aid!r}")
            by_id.pop(aid, None)
            continue
        if aid not in by_id:
            raise OverlayError(f"overlay references unknown assertion {aid!r}")
        target = by_id[aid]
        if "severity" in changed:
            new, floor = changed["severity"], floors.get(aid)
            if new not in _SEVERITY_RANK:
                # Unrecognized severity must be a policy error, not a KeyError
                # traceback (round-2 audit finding 1).
                raise OverlayError(
                    f"overlay sets unknown severity {new!r} for {aid!r}; "
                    f"expected one of {sorted(_SEVERITY_RANK)}")
            if floor and _SEVERITY_RANK[new] < _SEVERITY_RANK[floor]:
                raise OverlayError(
                    f"overlay lowers severity of {aid!r} below central floor "
                    f"{floor!r}")
            target["severity"] = new
        if "evaluator" in changed:
            eid = changed["evaluator"].get("id")
            if approved and eid not in approved:
                raise OverlayError(
                    f"overlay selects unapproved evaluator {eid!r} for {aid!r}")
            target["evaluator"] = changed["evaluator"]

    for added in overlay.get("add_assertions", []):
        if added["id"] in by_id:
            raise OverlayError(f"overlay redefines existing assertion {added['id']!r}")
        by_id[added["id"]] = added

    # A repository cannot reduce the grant set; grants come from the control plane.
    if overlay.get("capability_grants") or overlay.get("network"):
        raise OverlayError(
            "overlay may not grant network access or secrets; "
            "capabilities are control-plane policy")

    return [by_id[a["id"]] for a in assertions if a["id"] in by_id] + \
           [a for a in overlay.get("add_assertions", [])]


def load_overlay(root: str) -> dict:
    """Load an optional repository overlay from the policy root."""
    fp = Path(root).resolve() / "overlay.json"
    if not fp.exists():
        return {}
    try:
        return json.loads(fp.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise PolicyError(f"cannot read overlay {fp}: {e}") from e