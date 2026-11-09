#!/usr/bin/env python3
# spec: art-brief-01, art-brief-02, art-stage-01, art-ledger-01, art-rights-01
"""art_checks.py - declaration and inventory checks.

The title must declare its brief, its pipeline and its inventory before any
question about quality can be asked. These four checks establish that: the
brief exists, is versioned and carries a shape rule per class; every pipeline
stage names a consumer that exists; the ledger rows are complete and every
published count derives from them; rights is an explicit value.

Outcome checks (did the bytes survive, was it accepted, does it draw) live in
`art_check_outcome.py`. The entry point owns the exit-code contract. Split at
the source soft limit, the way the limit is meant to be used.

Enforcement is mechanical by design: the scanner checks that a fidelity verdict
exists and names a class rule, and cannot check that the verdict is correct.
That residual is the contract's, not this tool's to hide.
"""
from __future__ import annotations

import json
from pathlib import Path

LEDGER_MIN_FIELDS = (
    "id", "class", "stage", "brief_ref", "prompt", "seed",
    "digests", "prep_stages", "fidelity", "measurement", "rights",
)
DIGEST_STAGES = ("concept", "raw", "prepared", "albedo", "packed")
VERDICT_ACCEPT = "accept"
VERDICT_REJECT = "reject"


class Finding:
    __slots__ = ("req", "msg", "detail")

    def __init__(self, req: str, msg: str, detail: str = ""):
        self.req = req
        self.msg = msg
        self.detail = detail

    def line(self) -> str:
        extra = f"  [{self.detail}]" if self.detail else ""
        return f"art-scan: FAIL {self.req}: {self.msg}{extra}"


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return exc


def check_brief(cfg: dict, root: Path, rows: list, out: list) -> None:
    """art-brief-01, art-brief-02: a versioned brief, referenced, with a rule per class."""
    rel = cfg.get("brief")
    if not rel:
        out.append(Finding("art-brief-01", "no brief declared in the manifest"))
        return
    path = root / rel
    if not path.is_file():
        out.append(Finding("art-brief-01", f"brief not found: {rel}"))
        return
    if not cfg.get("brief_version"):
        out.append(Finding("art-brief-01", "brief is unversioned (manifest needs brief_version)"))
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    required = ("readability", "pillar", "palette", "shape language",
                "footprint", "material", "camera")
    for field in required:
        if field not in text:
            out.append(Finding("art-brief-01", f"brief is missing a required section: {field}"))
    rules = cfg.get("shape_rules") or {}
    classes = {str(r.get("class", "")) for r in rows}
    for cls in sorted(c for c in classes if c):
        if cls not in rules:
            out.append(Finding("art-brief-02",
                               f"no geometric rule declared for class '{cls}'"))
    ver = str(cfg.get("brief_version") or "")
    for r in rows:
        ref = str(r.get("brief_ref", ""))
        if not ref:
            out.append(Finding("art-brief-01", f"{r.get('id', '?')}: no brief_ref"))
        elif ver:
            # Exact suffix, not a substring. `ver in ref` accepted '@13', '@30'
            # and '@123' for version '3' - a brief_ref naming a different
            # version of the brief is not a reference to this one.
            if ref.split("@")[-1] != ver:
                out.append(Finding("art-brief-01",
                                   f"{r.get('id', '?')}: brief_ref '{ref}' "
                                   f"does not name version {ver}"))


def check_stages(cfg: dict, root: Path, out: list) -> list:
    """art-stage-01: every stage names a consumer that exists. Returns the stage enum."""
    stages = cfg.get("stages") or []
    if not stages:
        out.append(Finding("art-stage-01", "no pipeline stages declared"))
        return []
    enum = []
    for st in stages:
        name = st.get("name", "?")
        consumer = st.get("consumer")
        if not consumer or consumer in ("none", "null"):
            out.append(Finding("art-stage-01",
                               f"stage '{name}' names no consumer",
                               "a stage with no reader is not a stage"))
            continue
        cpath = root / consumer
        if not cpath.exists():
            out.append(Finding("art-stage-01",
                               f"stage '{name}' consumer path missing: {consumer}"))
            continue
        enum.append(name)
    return enum


def check_ledger(cfg: dict, root: Path, out: list) -> list:
    """art-ledger-01: rows complete, artifacts covered, counts derived."""
    rel = cfg.get("ledger")
    if not rel:
        out.append(Finding("art-ledger-01", "no ledger declared in the manifest"))
        return []
    data = load_json(root / rel)
    if isinstance(data, Exception):
        out.append(Finding("art-ledger-01", f"ledger unreadable: {data}"))
        return []
    rows = data.get("assets") if isinstance(data, dict) else data
    if not isinstance(rows, list) or not rows:
        out.append(Finding("art-ledger-01", "ledger has no asset rows"))
        return []
    seen = set()
    for r in rows:
        rid = str(r.get("id", "?"))
        if rid in seen:
            out.append(Finding("art-ledger-01", f"duplicate ledger row: {rid}"))
        seen.add(rid)
        for field in LEDGER_MIN_FIELDS:
            if field not in r:
                out.append(Finding("art-ledger-01", f"{rid}: missing field '{field}'"))
        # A blank stage is worse than a missing one. The key is present so the
        # completeness check passes, and every later stage test short-circuits
        # on the falsy value - which is how art-done-01, the contract's
        # centrepiece ("done means visible in a shipped build"), went green on
        # an asset with no stage at all.
        if "stage" in r and not str(r.get("stage") or "").strip():
            out.append(Finding("art-ledger-01", f"{rid}: stage is blank",
                               "done is a stage claim; a blank one is not a claim"))
        dig = r.get("digests") if isinstance(r.get("digests"), dict) else {}
        for stage in DIGEST_STAGES:
            if not dig.get(stage):
                out.append(Finding("art-ledger-01",
                                   f"{rid}: no digest for stage '{stage}'"))
    # An artifact on disk with no ledger row is an untracked asset.
    for art_dir in cfg.get("artifact_dirs") or []:
        d = root / art_dir
        if not d.is_dir():
            continue
        for child in sorted(d.iterdir()):
            if child.name.startswith("."):
                continue
            stem = child.stem if child.is_file() else child.name
            if stem not in seen and child.name not in seen:
                out.append(Finding("art-ledger-01",
                                   f"artifact outside the ledger: {child.relative_to(root)}"))
    # Counts published anywhere must derive from the ledger. A published figure
    # that disagrees is a doc-truth failure surfaced here as the count check.
    # Only labels with a declared derivation may be published at all: an
    # unknown label is a number with no way to check it, which is the failure
    # this rule exists to prevent.
    derivations = {"library": len(rows)}
    published = cfg.get("published_counts") or {}
    for label, value in published.items():
        if label not in derivations:
            out.append(Finding("art-ledger-01",
                               f"published count '{label}' has no declared derivation",
                               f"known labels: {', '.join(sorted(derivations))}"))
            continue
        # bool is a subclass of int in Python, and True == 1 - so a bare
        # `true` in the manifest would satisfy the compare below and report
        # a count that was never derived. 1.0 == 1 has the same shape. Reject
        # anything that is not a real int before the compare; pinned by the
        # `count-bool` / `count-float` / `count-string` fixtures.
        if isinstance(value, bool) or not isinstance(value, int):
            out.append(Finding("art-ledger-01", f"published count '{label}' is not an integer"))
            continue
        if value != derivations[label]:
            out.append(Finding("art-ledger-01",
                               f"published {label}={value} but the ledger derives "
                               f"{derivations[label]}",
                               "counts are derived, never typed"))
    return rows


def check_rights(rows: list, out: list) -> None:
    """art-rights-01: rights is an explicit value; a blank is invalid."""
    for r in rows:
        rid = str(r.get("id", "?"))
        if "rights" not in r:
            out.append(Finding("art-rights-01", f"{rid}: rights field absent"))
        elif r.get("rights") in (None, ""):
            out.append(Finding("art-rights-01",
                               f"{rid}: rights is blank - 'unknown' must be written explicitly"))
