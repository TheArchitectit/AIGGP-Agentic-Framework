#!/usr/bin/env python3
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
STAGE_FIELDS = ("input", "output", "determinism")
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


# spec: art-brief-01, art-brief-02
def check_brief(cfg: dict, root: Path, rows: list, out: list) -> None:
    """art-brief-01, art-brief-02: a versioned brief, referenced, with a rule per class."""
    rel = cfg.get("brief")
    if not isinstance(rel, str) or not rel:
        out.append(Finding("art-brief-01", "no brief declared in the manifest"))
        return
    path = root / rel
    if not path.is_file():
        out.append(Finding("art-brief-01", f"brief not found: {rel}"))
        return
    raw_ver = cfg.get("brief_version")
    ver = "" if raw_ver is None else str(raw_ver)
    # A version must be non-blank: whitespace is not a version.
    # `if not cfg.get("brief_version")` let "   " through, and a whitespace
    # brief_ref compared equal to it - two blanks agreeing on nothing, with
    # art-brief-01 green.
    if not ver.strip():
        out.append(Finding("art-brief-01", "brief is unversioned (manifest needs brief_version)"))
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    required = ("readability", "pillar", "palette", "shape language",
                "footprint", "material", "camera")
    for field in required:
        if field not in text:
            out.append(Finding("art-brief-01", f"brief is missing a required section: {field}"))
    raw_rules = cfg.get("shape_rules")
    rules = raw_rules if isinstance(raw_rules, dict) else {}
    # A rule is a non-blank string. `cls not in rules` below is key-presence
    # only, so `{"furniture": ""}` and `{"furniture": null}` declared a key
    # with no rule in it and art-brief-02 went green. Same falsy-short-circuit
    # class as the empty measurement: the declared value never entered a test
    # that could fail. Every declared value is checked, not just used classes.
    for cls, rule in sorted(rules.items()):
        if not isinstance(rule, str) or not rule.strip():
            out.append(Finding("art-brief-02",
                               f"class '{cls}' has no geometric rule "
                               f"(declared {rule!r})",
                               "a rule is a non-blank string"))
    # Strip before the set is built: a whitespace-only class is blank (the
    # ledger check names it) and must not demand a shape rule under the name
    # '  ' as a side effect.
    classes = {str(r.get("class", "")).strip() for r in rows}
    for cls in sorted(c for c in classes if c):
        if cls not in rules:
            out.append(Finding("art-brief-02",
                               f"no geometric rule declared for class '{cls}'"))
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


# spec: art-stage-01
def check_stages(cfg: dict, root: Path, out: list) -> list:
    """art-stage-01: every stage states input, output, its reader, determinism.

    A stage is four declarations, not a name. `spec.md` requires the input, the
    output, the code that reads that output, and the determinism requirement;
    a stage missing any of them is not a declared stage and must not enter the
    stage enum.
    """
    stages = cfg.get("stages")
    if not isinstance(stages, list) or not stages:
        out.append(Finding("art-stage-01", "no pipeline stages declared"))
        return []
    enum = []
    for st in stages:
        if not isinstance(st, dict):
            out.append(Finding("art-stage-01",
                               f"stage entry is not an object "
                               f"(type {type(st).__name__})"))
            continue
        name = st.get("name", "?")
        missing = [k for k in STAGE_FIELDS
                   if not isinstance(st.get(k), str) or not st.get(k).strip()]
        if missing:
            out.append(Finding("art-stage-01",
                               f"stage '{name}' does not state: {', '.join(missing)}",
                               "a stage is input, output, reader and determinism"))
            continue
        consumer = st.get("consumer")
        if (not isinstance(consumer, str) or not consumer.strip()
                or consumer in ("none", "null")):
            out.append(Finding("art-stage-01",
                               f"stage '{name}' names no consumer",
                               "a stage with no reader is not a stage"))
            continue
        cpath = root / consumer
        # The consumer is "the code that reads that output" (spec.md). A
        # directory exists on disk and reads nothing; `exists()` accepted it.
        if not cpath.is_file():
            out.append(Finding("art-stage-01",
                               f"stage '{name}' consumer is not a file: {consumer}",
                               "the consumer is the code that reads the output"))
            continue
        enum.append(name)
    return enum


# spec: art-ledger-01
def check_ledger(cfg: dict, root: Path, out: list) -> list:
    """art-ledger-01: rows complete, artifacts covered, counts derived."""
    rel = cfg.get("ledger")
    if not isinstance(rel, str) or not rel:
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
    records = []
    seen = set()
    for idx, r in enumerate(rows):
        # A row is an object. A string (or list, number) is valid JSON and
        # nothing else, and used to reach `r.get(...)` below as a traceback
        # with no requirement named. Name the row and keep scanning.
        if not isinstance(r, dict):
            out.append(Finding("art-ledger-01",
                               f"ledger row {idx} is not a JSON object "
                               f"(type {type(r).__name__})",
                               "a row is an object; anything else is a shape error"))
            continue
        records.append(r)
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
        # Completeness is not presence. `"prompt": ""` and `"seed": null`
        # satisfied the `field not in r` loop above while carrying nothing: a
        # blank prompt names no generation and a null seed seeds no run.
        if "prompt" in r and (not isinstance(r.get("prompt"), str)
                              or not r["prompt"].strip()):
            out.append(Finding("art-ledger-01", f"{rid}: prompt is blank",
                               "the ledger records what was asked for"))
        if "seed" in r:
            seed = r["seed"]
            if isinstance(seed, bool) or not isinstance(seed, int):
                out.append(Finding("art-ledger-01",
                                   f"{rid}: seed is not an integer "
                                   f"(type {type(seed).__name__})",
                                   "a seed seeds a reproducible run; null seeds nothing"))
        # An asset with no class never requires a shape rule (art-brief-02) and
        # acceptance is never checked against a class (art-accept-01), so a
        # blank class was a quiet bypass of both.
        if "class" in r and not str(r.get("class") or "").strip():
            out.append(Finding("art-ledger-01", f"{rid}: class is blank",
                               "no class means no shape rule to be accepted against"))
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
    derivations = {"library": len(records)}
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
    return records


# spec: art-rights-01
def check_rights(rows: list, out: list) -> None:
    """art-rights-01: rights is an explicit value; a blank is invalid."""
    for r in rows:
        rid = str(r.get("id", "?"))
        if "rights" not in r:
            out.append(Finding("art-rights-01", f"{rid}: rights field absent"))
        # Blank after strip, not equality with "". `"   "` is not a rights
        # classification and used to pass as one.
        elif not str(r.get("rights") or "").strip():
            out.append(Finding("art-rights-01",
                               f"{rid}: rights is blank - 'unknown' must be written explicitly"))
