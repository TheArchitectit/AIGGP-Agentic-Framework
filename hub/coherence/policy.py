# // spec: coh-pol-01, coh-pol-02, coh-pol-03
"""Policy resolution and adoption-ladder inputs.

Resolution verifies policy IDENTITY (content digest matches the expected
digest) and AUTHORITY (the context-bound anti-rollback record, design.md
round-15: the pinned bundle must be the control-plane-bound current central
bundle and meet the bound epoch floor, unless a recorded grandfather window
covers it). Baseline/exception sets load from the policy root; their digests
are separately bound in the signed context (coh-ctx-01).
"""
import json
from datetime import datetime
from pathlib import Path

from . import canon


class PolicyError(ValueError):
    """Policy resolution failure (exit-31 class)."""


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def check_advisory_escalation(bundle: dict) -> dict:
    """The bundle's advisory-age escalation policy (design.md round-16).

    `stages.max_advisory_age_days` is a duration, not a consequence. A bundle
    that declares the cap must also declare `advisory_escalation` — the field
    is required whenever `stages` is present, because naming a dwell limit
    with no policy for exceeding it is incomplete configuration, and silence
    must not read as "cap declared, nothing happens". Refuses (exit 31,
    `advisory-escalation:` prefix) rather than defaulting.

    A bundle with no `stages` has no cap and nothing to escalate; that is the
    one shape where absence is meaningful. Returns the policy (possibly {}).
    """
    if not isinstance(bundle, dict):
        raise PolicyError("advisory-escalation: policy bundle is not an object")
    if "stages" not in bundle:
        return {}
    esc = bundle.get("advisory_escalation")
    if esc is None:
        raise PolicyError(
            "advisory-escalation: bundle declares stages.max_advisory_age_days "
            "but no advisory_escalation policy for exceeding it (coh-pol-03)")
    if not isinstance(esc, dict):
        raise PolicyError(
            "advisory-escalation: advisory_escalation must be an object")
    if esc.get("on_expiry") not in _ON_EXPIRY:
        raise PolicyError(
            f"advisory-escalation: on_expiry must be one of "
            f"{sorted(_ON_EXPIRY)}, got {esc.get('on_expiry')!r}")
    renewal = esc.get("renewal")
    if renewal is not None:
        if not isinstance(renewal, dict):
            raise PolicyError("advisory-escalation: renewal must be an object")
        if renewal.get("requires") not in _RENEWAL_REQUIRES:
            raise PolicyError(
                f"advisory-escalation: renewal.requires must be one of "
                f"{sorted(_RENEWAL_REQUIRES)}, got {renewal.get('requires')!r}")
        days = renewal.get("max_extension_days")
        if not isinstance(days, int) or isinstance(days, bool) or days < 1:
            raise PolicyError(
                f"advisory-escalation: renewal.max_extension_days must be a "
                f"positive integer, got {days!r}")
    return esc


def check_anti_rollback(digest: str, bundle: dict, binding: dict,
                        evaluation_time: str) -> None:
    """Run-path anti-rollback (design.md round-15, coh-pol-01/02).

    The pinned bundle must match the context-bound `expected_digest` AND
    declare a `bundle_epoch` at or above the bound `min_bundle_epoch` —
    unless a grandfather record covers exactly this content within its
    window (expiry measured against the context's evaluation_time, never
    the host clock). A grandfathered bundle is the one exception to both
    checks. Raises PolicyError with `anti-rollback:` / `policy-substitution:`
    reason prefixes so fleet reporting can alert on the attempt.
    """
    if not isinstance(binding, dict) or not binding:
        raise PolicyError(
            "policy-substitution: context binds no central policy (coh-pol-02); "
            "refusing to evaluate against repository-chosen policy")
    expected = binding.get("expected_digest")
    if not isinstance(expected, str) or not expected:
        raise PolicyError(
            "anti-rollback: bound expected_digest is missing or malformed")
    grandfathered = False
    if digest != expected:
        matches = []
        for g in binding.get("grandfathers") or []:
            if not isinstance(g, dict) or not isinstance(g.get("valid_until"), str):
                raise PolicyError(
                    "anti-rollback: malformed grandfather record")
            if g.get("bundle_digest") == digest:
                matches.append(g)
        if not matches:
            raise PolicyError(
                f"anti-rollback: pinned bundle digest {digest} is not the bound "
                f"central bundle {expected} and no grandfather window covers it "
                f"(coh-pol-01)")
        if evaluation_time is None:
            raise PolicyError(
                "anti-rollback: grandfather window present but the context "
                "carries no evaluation_time to judge expiry against")
        try:
            now = _parse(evaluation_time)
        except ValueError:
            raise PolicyError(
                "anti-rollback: context evaluation_time is unparseable") from None
        try:
            unexpired = [_parse(g["valid_until"]) > now for g in matches]
        except ValueError:
            raise PolicyError(
                "anti-rollback: grandfather window has an unparseable "
                "valid_until") from None
        if not any(unexpired):
            raise PolicyError(
                f"anti-rollback: grandfather window for {digest} expired at "
                f"{max(g['valid_until'] for g in matches)} (coh-pol-01)")
        grandfathered = True
    if grandfathered:
        return
    epoch = bundle.get("bundle_epoch")
    if not _is_int(epoch) or epoch < 0:
        raise PolicyError(
            "anti-rollback: bundle does not declare a valid bundle_epoch "
            "(coh-pol-01)")
    floor = binding.get("min_bundle_epoch", 0)
    if not _is_int(floor) or floor < 0:
        raise PolicyError(
            "anti-rollback: bound min_bundle_epoch is malformed")
    if epoch < floor:
        raise PolicyError(
            f"anti-rollback: pinned bundle epoch {epoch} is below the bound "
            f"floor {floor} (coh-pol-01)")


def resolve(root: str, expected_digest: str, binding: dict = None,
            evaluation_time: str = None) -> dict:
    """Resolve policy content and verify identity, then authority.

    Identity: the computed content digest must match the caller's expected
    digest. Authority (round-15): the context-bound anti-rollback record must
    accept the pinned content — `binding=None` is a substitution refusal, so
    a caller that forgets the binding fails closed rather than evaluating
    identity-only policy.

    Returns the policy bundle plus its computed digest. Raises PolicyError on
    missing content, digest mismatch, or an anti-rollback rejection.
    """
    root_p = Path(root).resolve()
    if not root_p.is_dir():
        raise PolicyError(f"policy root is not a directory: {root!r}")

    bundle_path = root_p / "policy.json"
    if not bundle_path.exists():
        raise PolicyError(f"missing policy bundle: {bundle_path}")

    try:
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
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

    check_anti_rollback(computed, bundle, binding, evaluation_time)
    check_advisory_escalation(bundle)

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
        data = json.loads(path.read_text(encoding="utf-8"))
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


# The Q2 freeze (s1-freeze-record.md): the assertion classes whose baseline
# shelter ends at Stage 3 unless central policy names another set. Matched
# by evaluator ID — the identity every assertion already carries, so a
# repository cannot relabel a core assertion out of the core.
DEFAULT_ENFORCED_CORE = frozenset({
    "devgate.builtin.identity-consistency",
    "devgate.builtin.traceability-completeness",
    "devgate.builtin.release-claim-consistency",
})


def enforced_core_classes(bundle: dict) -> frozenset:
    """The enforced-core evaluator set from the bundle's stages data
    (design.md round-14), or the Q2-freeze default when unset."""
    raw = (bundle.get("stages") or {}).get("enforced_core_classes")
    if raw is None:
        return DEFAULT_ENFORCED_CORE
    if not isinstance(raw, list) or not raw:
        raise PolicyError(
            "stages.enforced_core_classes must be a non-empty array")
    if not all(isinstance(c, str) and c for c in raw):
        raise PolicyError(
            "stages.enforced_core_classes members must be non-empty strings")
    return frozenset(raw)


# Severity ordering: a repository may raise severity, never lower it.
_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}

# Advisory-age escalation vocabulary (design.md round-16). `block` alone
# today: the ratified model picked one value that means what coh-pol-03's
# spec says over pre-guessing a ladder of synonyms. `central-approval` is
# the only renewal authority — a repository cannot renew its own advisory.
_ON_EXPIRY = frozenset({"block"})
_RENEWAL_REQUIRES = frozenset({"central-approval"})


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

    if not isinstance(overlay, dict):
        raise OverlayError("overlay must be an object")
    # Every entry below is repository-authored policy input; `.get`/`["id"]` on
    # a bare string or int is an uncaught AttributeError/TypeError (exit 1, no
    # envelope) — shape is pinned here, before any field is read, so a
    # malformed overlay is exit 31 like every other policy refusal.
    for key in ("assertions", "add_assertions"):
        if not isinstance(overlay.get(key, []), list):
            raise OverlayError(f"overlay {key} must be an array")
    for changed in overlay.get("assertions", []):
        if not isinstance(changed, dict) or not isinstance(changed.get("id"), str):
            raise OverlayError("overlay assertion entry must be an object with a string id")
        aid = changed["id"]
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
            # The severity hole got its guard in round 2; the evaluator sibling
            # never did — a non-object evaluator reached `.get("id")` and
            # crashed before the approved-list lookup could decide.
            ev = changed["evaluator"]
            if not isinstance(ev, dict) or not isinstance(ev.get("id"), str) or not ev["id"]:
                raise OverlayError(
                    f"overlay sets malformed evaluator reference for {aid!r}")
            eid = ev["id"]
            if approved and eid not in approved:
                raise OverlayError(
                    f"overlay selects unapproved evaluator {eid!r} for {aid!r}")
            target["evaluator"] = ev

    for added in overlay.get("add_assertions", []):
        if not isinstance(added, dict) or not isinstance(added.get("id"), str):
            raise OverlayError("overlay add_assertions entry must be an object with a string id")
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
        return json.loads(fp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise PolicyError(f"cannot read overlay {fp}: {e}") from e