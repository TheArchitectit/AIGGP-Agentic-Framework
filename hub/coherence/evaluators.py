# // spec: coh-assert-02, coh-assert-03, coh-assert-04, coh-assert-06, coh-eval-04, coh-eval-06, coh-rt-03, coh-ctx-04
"""Built-in slice evaluators: product-identity consistency, traceability
completeness, release-claim consistency, captured-fact consistency.
Deterministic, no network, no secrets. Each returns a list of findings
(empty = satisfied). All take (assertion, package, subject_root, facts) —
`facts` carries only the captured facts the assertion's subjects declared.
"""
import re
from pathlib import Path


class Unresolved(Exception):
    """Raised by an evaluator when the assertion cannot be decided.

    Per coh-assert-02 an unresolvable input (e.g. an empty selector) is
    UNRESOLVED, never VIOLATED and never SATISFIED. Defined here (not in
    evaluate.py) to avoid a circular import.
    """

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# Identity: compare declared fields against the approved package value, not
# merely against each other (coh-assert-02).
def identity_consistency(assertion: dict, package: dict, subject_root: str,
                         facts: dict = None) -> list:
    findings = []
    approved_ref = assertion["parameters"].get("approved_value_ref")
    approved = _dig(package, approved_ref) if approved_ref else None
    if approved is None:
        raise Unresolved(f"approved-value-missing:{approved_ref}")
    for sel in assertion["subjects"]:
        observed = _extract(sel, subject_root, package)
        if observed is None:
            # coh-assert-02: an empty selector is UNRESOLVED, not VIOLATED.
            raise Unresolved(f"selector-empty:{_loc(sel)}")
        if observed != approved:
            findings.append(_mk(assertion, "identity-mismatch",
                                expected=str(approved), observed=str(observed),
                                locations=[_loc(sel)]))
    return findings


# Traceability: every testable requirement has an assertion; every assertion
# traces to a normative requirement (coh-assert-04, coh-eval-04). The
# registry half runs here; the planning-time half runs in plan.py.
# parameters.marker_scan additionally consumes this repo's marker
# convention (mirrors scripts/spec_traceability.py): a testable requirement
# id must be claimed by a `// spec: <id>` marker in subject source.
def traceability_completeness(assertion: dict, package: dict, subject_root: str,
                              facts: dict = None) -> list:
    findings = []
    reqs = package.get("normative_requirements") or {}
    for rid, meta in reqs.items():
        if meta.get("testable") and not meta.get("assertion_ids"):
            findings.append(_mk(assertion, "orphan-requirement",
                                expected="an assertion", observed=f"requirement {rid} untestable"))
    if assertion.get("parameters", {}).get("marker_scan"):
        marked = _source_markers(subject_root)
        for rid, meta in reqs.items():
            if meta.get("testable") and rid not in marked:
                findings.append(_mk(assertion, "unmarked-requirement",
                                    expected=f"// spec: {rid} in subject source",
                                    observed="no marker in subject tree",
                                    locations=[rid]))
    return findings


# Marker grammar mirrors scripts/spec_traceability.py (kept in lockstep):
# one marker line may carry several comma-separated ids, and the comma anchor
# keeps a trailing comment (`// spec: a-01 -- why`) out of the captured ids.
# Both `//` and `#` comment prefixes count (H6: `//`-only locked Python
# subjects out of marker coverage).
MARKER_RE = re.compile(r"(?://|#)\s*spec:[ \t]*([a-z0-9-]+(?:[ \t]*,[ \t]*[a-z0-9-]+)*)")
MARKER_ID_RE = re.compile(r"[a-z0-9-]+")
MARKER_EXTS = {".rs", ".py", ".mjs", ".js", ".ts"}
MARKER_SKIP = {"target", "node_modules", ".git", "openspec", ".devgate"}


def _source_markers(subject_root: str) -> set:
    root = Path(subject_root)
    if not root.is_dir():
        # Unresolvable input is UNRESOLVED, never VIOLATED (coh-assert-02):
        # scanning a missing tree would report every requirement unmarked.
        raise Unresolved(f"subject-root-missing:{subject_root}")
    markers = set()
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in MARKER_EXTS:
            continue
        if MARKER_SKIP & set(path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for group in MARKER_RE.findall(text):
            markers.update(MARKER_ID_RE.findall(group))
    return markers


# Release-claim: bind manifest to inner payload digest, forbid self-reference
# (coh-assert-03).
def release_claim_consistency(assertion: dict, package: dict, subject_root: str,
                              facts: dict = None) -> list:
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


# Captured-fact consistency (coh-rt-03, coh-ctx-04): the approved external
# lookup ran OUTSIDE the evaluator as a capture step; its digest-verified
# response content is bound in the context and replayed here — never a live
# fetch (default-deny: this module has no network path at all).
def captured_fact_consistency(assertion: dict, package: dict, subject_root: str,
                              facts: dict = None) -> list:
    facts = facts or {}
    approved_ref = assertion["parameters"].get("approved_value_ref")
    approved = _dig(package, approved_ref) if approved_ref else None
    if approved is None:
        raise Unresolved(f"approved-value-missing:{approved_ref}")
    field = assertion["parameters"].get("response_field", "value")
    findings = []
    for sel in assertion["subjects"]:
        if sel.get("kind") != "captured-fact":
            continue
        fact = facts.get(sel.get("fact_id"))
        if fact is None:
            raise Unresolved(f"captured-fact-missing:{sel.get('fact_id')}")
        observed = _dig(fact, field) if isinstance(fact, dict) else None
        if observed is None:
            raise Unresolved(f"captured-fact-field-empty:{field}")
        if observed != approved:
            findings.append(_mk(assertion, "captured-fact-mismatch",
                                expected=str(approved), observed=str(observed),
                                locations=[_loc(sel)]))
    return findings


BUILTINS = {
    "devgate.builtin.identity-consistency": identity_consistency,
    "devgate.builtin.traceability-completeness": traceability_completeness,
    "devgate.builtin.release-claim-consistency": release_claim_consistency,
    "devgate.builtin.captured-fact-consistency": captured_fact_consistency,
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
        "violation_class": violation_class,
        "outcome": "VIOLATED",
        "enforcement": "BLOCK",
        "severity": assertion.get("severity", "medium"),
        "subject_locations": locs,
        "expected": expected,
        "observed": observed,
        "evidence_refs": [],
    }
