# // spec: coh-assert-02, coh-assert-03, coh-assert-04, coh-assert-05, coh-assert-06, coh-eval-04, coh-eval-06, coh-rt-03, coh-ctx-04, coh-3d-02, coh-3d-03, coh-3d-04
"""Built-in slice evaluators: product-identity consistency, traceability
completeness, release-claim consistency, captured-fact consistency, 3D room
coherence, and vision observation posture. Deterministic, no network, no
secrets. Each returns a list of findings (empty = satisfied). All take
(assertion, package, subject_root, facts) — `facts` carries only the captured
facts the assertion's subjects declared.
"""
import json
import re
from pathlib import Path

from . import canon, manifest


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
MARKER_EXTS = {".rs", ".py", ".mjs", ".js", ".ts", ".sh", ".zig"}
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


_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def builtin_evaluator_digest() -> str:
    """Real digest of this evaluator artifact (this file's bytes).

    A claim about which evaluator ran is only meaningful bound to the code
    that runs; absence is loud, never a placeholder digest."""
    return manifest._digest_file(Path(__file__))


def _read_contained_bytes(subject_root: str, rel: str) -> bytes:
    if not rel or not isinstance(rel, str):
        raise Unresolved("selector-empty:?")
    root = Path(subject_root).resolve()
    try:
        resolved = (root / rel).resolve()
    except (OSError, ValueError):
        raise Unresolved(f"selector-unresolvable:{rel}")
    if root not in resolved.parents and resolved != root:
        raise Unresolved(f"selector-escapes-subject:{rel}")
    fp = root / rel
    if not fp.is_file():
        raise Unresolved(f"selector-empty:{rel}")
    return fp.read_bytes()


def _read_contained_json(subject_root: str, rel: str) -> dict:
    raw = _read_contained_bytes(subject_root, rel)
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise Unresolved(f"selector-unparseable:{rel}")
    if not isinstance(doc, dict):
        raise Unresolved(f"selector-not-object:{rel}")
    return doc


# 3D room coherence (coh-3d-02, coh-3d-03, coh-3d-04): pure evaluation over
# declared world-bundle parts and pinned capture records — never renders or
# invokes simulation.
def world_room_coherence(assertion: dict, package: dict, subject_root: str,
                         facts: dict = None) -> list:
    params = assertion.get("parameters") or {}
    check = params.get("check")
    bundle_rel = params.get("bundle_path", "world-bundle.json")
    bundle = _read_contained_json(subject_root, bundle_rel)
    parts = bundle.get("parts")
    if not isinstance(parts, list):
        raise Unresolved(f"world-bundle-parts-missing:{bundle_rel}")
    by_id = {p.get("part_id"): p for p in parts
             if isinstance(p, dict) and isinstance(p.get("part_id"), str)}
    by_kind = {}
    for p in parts:
        if isinstance(p, dict) and isinstance(p.get("kind"), str):
            by_kind.setdefault(p["kind"], []).append(p)

    findings = []
    if check == "parts-complete":
        req_kinds = params.get("required_part_kinds") or [
            "world-ir", "glb", "engine-scene",
            "executable-build", "capture", "evaluation-record"]
        for k in req_kinds:
            if k not in by_kind:
                findings.append(_mk(assertion, "missing-world-part",
                                    expected=f"part kind {k}",
                                    observed="absent from world-bundle.json",
                                    locations=[bundle_rel]))
        for p in parts:
            if not isinstance(p, dict):
                continue
            rel = p.get("path")
            if isinstance(rel, str):
                _read_contained_bytes(subject_root, rel)
        return findings

    if check == "room-bounds":
        ir_rel = (by_kind.get("world-ir") or [{}])[0].get("path")
        ir = _read_contained_json(subject_root, ir_rel)
        exp_id = _dig(package, params.get("approved_room_id_ref", ""))
        obs_id = ir.get("room_id")
        if exp_id is not None and obs_id != exp_id:
            findings.append(_mk(assertion, "room-id-mismatch",
                                expected=str(exp_id), observed=str(obs_id),
                                locations=[ir_rel]))
        dims = ir.get("bounds_mm") or {}
        min_dims = params.get("min_bounds_mm") or {}
        for axis in ("width", "depth", "height"):
            if axis in min_dims:
                val = dims.get(axis)
                floor = min_dims[axis]
                if (not isinstance(val, int) or isinstance(val, bool)
                        or val < floor):
                    findings.append(_mk(
                        assertion, "room-bounds-violation",
                        expected=f"{axis}>={floor}",
                        observed=f"{axis}={val!r}",
                        locations=[ir_rel]))
        return findings

    if check == "doorway-clearance":
        ir_rel = (by_kind.get("world-ir") or [{}])[0].get("path")
        cap_part = by_id.get(params.get("capture_part_id", "")) or (
            (by_kind.get("capture") or [{}])[0])
        cap_rel = cap_part.get("path")
        cfg_rel = cap_part.get("capture_config_path")
        ir = _read_contained_json(subject_root, ir_rel)
        cap = _read_contained_json(subject_root, cap_rel)
        _read_contained_bytes(subject_root, cfg_rel)
        cfg_digest = manifest._digest_file(Path(subject_root).resolve() / cfg_rel)
        if cap.get("capture_config_digest") != cfg_digest:
            findings.append(_mk(
                assertion, "capture-config-digest-mismatch",
                expected=cfg_digest,
                observed=str(cap.get("capture_config_digest")),
                locations=[cap_rel]))
        min_clear = params.get("min_clear_width_mm", 1200)
        ir_clear = (ir.get("doorway") or {}).get("clear_width_mm")
        cap_clear = (cap.get("measurements") or {}).get(
            "doorway_clear_width_mm")
        blocked = bool((cap.get("measurements") or {}).get("doorway_blocked"))
        if (not isinstance(ir_clear, int) or isinstance(ir_clear, bool)
                or ir_clear < min_clear
                or not isinstance(cap_clear, int)
                or isinstance(cap_clear, bool)
                or cap_clear < min_clear or blocked):
            findings.append(_mk(
                assertion, "doorway-clearance-violation",
                expected=f"clear_width_mm>={min_clear} and doorway_blocked=False "
                         f"(config={cfg_digest})",
                observed=f"ir={ir_clear!r}, capture={cap_clear!r}, "
                         f"blocked={blocked} (config={cfg_digest})",
                locations=[cap_rel]))
        return findings

    if check == "asset-scene-binding":
        glb_part = (by_kind.get("glb") or [{}])[0]
        scn_part = (by_kind.get("engine-scene") or [{}])[0]
        glb_rel = glb_part.get("path")
        scn_rel = scn_part.get("path")
        glb_bytes = _read_contained_bytes(subject_root, glb_rel)
        if len(glb_bytes) < 12 or glb_bytes[:4] != b"glTF":
            findings.append(_mk(assertion, "invalid-glb-header",
                                expected="glTF 2.0 binary magic",
                                observed=f"header={glb_bytes[:4]!r}",
                                locations=[glb_rel]))
        scn_text = _read_contained_bytes(subject_root, scn_rel).decode(
            "utf-8", errors="replace")
        if glb_rel not in scn_text:
            findings.append(_mk(
                assertion, "scene-asset-unbound",
                expected=f"scene references {glb_rel}",
                observed="GLB path absent from engine scene",
                locations=[scn_rel]))
        return findings

    raise Unresolved(f"unknown-world-room-check:{check!r}")


def _artifact_matches(subject_root: str, rel: str, claimed: str) -> bool:
    """Value check: artifact bytes under `rel` hash to `claimed`; unreadable
    or missing artifacts fail verification (unverified is never pinned)."""
    if not isinstance(rel, str) or not rel:
        return False
    try:
        return manifest._digest_file(
            Path(subject_root).resolve() / rel) == claimed
    except (OSError, ValueError):
        return False


def is_pinned_reproducible_model(assertion: dict, facts: dict = None,
                                 subject_root: str = None) -> bool:
    """True iff a model/vision observation is pinned AND verified (coh-assert-05).

    Shape alone never pins: claimed rubric/model digests must match the real
    artifacts they name under `subject_root`, the claimed evaluator digest
    must match this evaluator artifact, and the captured fact must echo every
    pin plus an integer seed. Any gap is unpinned — advisory, never enforced.
    """
    facts = facts or {}
    params = assertion.get("parameters") or {}
    rubric = params.get("rubric_digest")
    model = params.get("model_digest")
    seed = params.get("seed")
    if (not isinstance(rubric, str) or not _DIGEST_RE.fullmatch(rubric)
            or not isinstance(model, str) or not _DIGEST_RE.fullmatch(model)
            or not isinstance(seed, int) or isinstance(seed, bool)):
        return False
    if not subject_root:
        return False
    try:
        if ((assertion.get("evaluator") or {}).get("digest")
                != builtin_evaluator_digest()):
            return False
    except OSError:
        return False
    if not _artifact_matches(subject_root, params.get("rubric_path"), rubric):
        return False
    if not _artifact_matches(subject_root, params.get("model_path"), model):
        return False
    sels = [s for s in (assertion.get("subjects") or [])
            if isinstance(s, dict) and s.get("kind") == "captured-fact"]
    if not sels:
        return False
    for sel in sels:
        fact = facts.get(sel.get("fact_id"))
        if not isinstance(fact, dict):
            return False
        inp = fact.get("input_digest")
        if (fact.get("reproducible") is False
                or fact.get("rubric_digest") != rubric
                or fact.get("model_digest") != model
                or fact.get("seed") != seed
                or not isinstance(inp, str)
                or not _DIGEST_RE.fullmatch(inp)):
            return False
        if fact.get("input_path") is not None and not _artifact_matches(
                subject_root, fact.get("input_path"), inp):
            return False
    return True


# Vision/model observation posture (coh-assert-05): unpinned or stochastic
# observations remain non-canonical advisory evidence and never block or
# silently produce an enforced PASS; fully pinned reproducible observations
# participate deterministically under the normal contract.
def vision_observation(assertion: dict, package: dict, subject_root: str,
                       facts: dict = None) -> list:
    facts = facts or {}
    params = assertion.get("parameters") or {}
    expected_verdict = params.get("expected_verdict", "clear")
    pinned = is_pinned_reproducible_model(assertion, facts, subject_root)
    findings = []
    for sel in assertion.get("subjects") or []:
        if sel.get("kind") != "captured-fact":
            continue
        fid = sel.get("fact_id")
        fact = facts.get(fid)
        if not isinstance(fact, dict):
            raise Unresolved(f"captured-fact-missing:{fid}")
        verdict = fact.get("verdict")
        summary = fact.get("observation", str(verdict))
        if not pinned:
            f = _mk(assertion, "unpinned-model-advice",
                    expected=f"pinned reproducible rubric ({expected_verdict})",
                    observed=f"advisory-only vision observation: {summary}",
                    locations=[fid or "vision-fact"])
            f["enforcement"] = "ADVISORY"
            findings.append(f)
        elif verdict != expected_verdict:
            findings.append(_mk(
                assertion, "vision-rubric-violation",
                expected=str(expected_verdict),
                observed=str(verdict),
                locations=[fid or "vision-fact"]))
    return findings


BUILTINS = {
    "devgate.builtin.identity-consistency": identity_consistency,
    "devgate.builtin.traceability-completeness": traceability_completeness,
    "devgate.builtin.release-claim-consistency": release_claim_consistency,
    "devgate.builtin.captured-fact-consistency": captured_fact_consistency,
    "devgate.builtin.world-room-coherence": world_room_coherence,
    "devgate.builtin.vision-observation": vision_observation,
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

    Selector paths are repository-supplied content and are CONTAINED under the
    subject root before any read (coh-sec-01): traversal, absolute paths, and
    symlink escapes are UNRESOLVED with a stable reason — never reads outside
    the subject tree (audit finding F4: a hostile selector could exfiltrate
    host files into findings and sealed evidence).
    """
    kind = selector.get("kind")
    if kind == "artifact-metadata":
        return _dig(package, selector.get("selector", ""))
    if kind == "file":
        path = selector.get("path")
        if not path or not isinstance(path, str):
            return None
        root = Path(subject_root).resolve()
        try:
            resolved = (root / path).resolve()
        except (OSError, ValueError):
            raise Unresolved(f"selector-unresolvable:{path}")
        if root not in resolved.parents and resolved != root:
            raise Unresolved(f"selector-escapes-subject:{path}")
        fp = root / path
        if not fp.exists():
            return None
        # An existing path that is not a readable file is not an empty
        # resolution: the evaluator's own read is what fails, and that OSError
        # is a real crash (ERROR-execution, coh-dec-01) — not selector-empty.
        text = fp.read_text(encoding="utf-8", errors="replace")
        m = _IDENTITY_RE.search(text)
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
