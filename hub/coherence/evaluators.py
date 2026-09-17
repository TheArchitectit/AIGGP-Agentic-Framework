# // spec: coh-assert-02, coh-assert-03, coh-assert-04, coh-eval-06
"""Built-in slice evaluators: product-identity consistency, traceability
completeness, release-claim consistency. Deterministic, no network, no secrets.
Each returns a list of findings (empty = satisfied).
"""
import re
from pathlib import Path

# Identity: compare declared fields against the approved package value, not
# merely against each other (coh-assert-02).
def identity_consistency(assertion: dict, package: dict, subject_root: str) -> list:
    findings = []
    approved_ref = assertion["parameters"].get("approved_value_ref")
    approved = _dig(package, approved_ref) if approved_ref else None
    if approved is None:
        return [_mk(assertion, "selector-empty",
                    expected=f"approved value at {approved_ref}",
                    observed="no approved value in package")]
    for sel in assertion["subjects"]:
        observed = _extract(sel, subject_root, package)
        if observed is None:
            findings.append(_mk(assertion, "selector-empty",
                                expected=str(approved), observed="selector empty"))
        elif observed != approved:
            findings.append(_mk(assertion, "identity-mismatch",
                                expected=str(approved), observed=str(observed),
                                locations=[_loc(sel)]))
    return findings


# Traceability: every testable requirement has an assertion; every assertion
# traces to a normative requirement (coh-assert-04). Planning-time structure.
def traceability_completeness(assertion: dict, package: dict, subject_root: str) -> list:
    findings = []
    reqs = package.get("normative_requirements") or {}
    for rid, meta in reqs.items():
        if meta.get("testable") and not meta.get("assertion_ids"):
            findings.append(_mk(assertion, "orphan-requirement",
                                expected="an assertion", observed=f"requirement {rid} untestable"))
    return findings


# Release-claim: bind manifest to inner payload digest, forbid self-reference
# (coh-assert-03).
def release_claim_consistency(assertion: dict, package: dict, subject_root: str) -> list:
    findings = []
    manifest = package.get("release_manifest")
    if manifest is None:
        return [_mk(assertion, "selector-empty", expected="release manifest",
                    observed="none in package")]
    inner = manifest.get("payload_digest")
    outer = manifest.get("subject_digest")
    if outer and outer == inner:
        findings.append(_mk(assertion, "self-referential-release",
                            expected="inner payload digest distinct from subject",
                            observed="manifest claims digest of bundle containing it"))
    return findings


BUILTINS = {
    "devgate.builtin.identity-consistency": identity_consistency,
    "devgate.builtin.traceability-completeness": traceability_completeness,
    "devgate.builtin.release-claim-consistency": release_claim_consistency,
}


def _dig(obj: dict, ref: str):
    if not ref:
        return None
    cur = obj
    for part in ref.split(":")[-1].split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


_IDENTITY_RE = re.compile(r"^#\s*(?:product|name)\s*[:=]\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


def _extract(selector: dict, subject_root: str, package: dict):
    """Extract a declared value from the subject or package.

    file: read the named file under subject_root and pull a declared
    `# product: <name>` metadata line (versioned extraction rule
    `structured-metadata`). artifact-metadata: dig the package by selector.
    Empty resolution returns None (callers map to UNRESOLVED/selector-empty).
    """
    kind = selector.get("kind")
    if kind == "artifact-metadata":
        return _dig(package, selector.get("selector", ""))
    if kind == "file":
        path = selector.get("path")
        if not path:
            return None
        fp = Path(subject_root) / path
        if not fp.exists():
            return None
        m = _IDENTITY_RE.search(fp.read_text(encoding="utf-8", errors="replace"))
        return m.group(1) if m else None
    return None


def _loc(sel: dict) -> str:
    return sel.get("path") or sel.get("selector") or "?"


def _mk(assertion: dict, violation_class: str, expected: str, observed: str,
        locations=None) -> dict:
    locs = locations or [_loc(s) for s in assertion.get("subjects", [])]
    key = "|".join([assertion["id"], locs[0] if locs else "?", violation_class])
    return {
        "assertion_id": assertion["id"],
        "finding_key": key,
        "outcome": "VIOLATED",
        "enforcement": "BLOCK",
        "severity": assertion.get("severity", "medium"),
        "subject_locations": locs,
        "expected": expected,
        "observed": observed,
        "evidence_refs": [],
    }
