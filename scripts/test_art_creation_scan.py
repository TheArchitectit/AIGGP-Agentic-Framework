#!/usr/bin/env python3
"""Fixture suite for art_creation_scan.py - the negatives that pin each rule.

Every case runs through the real `run_checks` against a real temp tree
(AGENTS.md: build fixtures by calling the real function; a case that only
exercises a stub proves nothing about the scanner). Each case carries the
EXACT requirement set it must trip - not just "there was a finding". A
fixture that regressed to trip a second requirement, or the wrong one, fails
here; asserting only pass/fail is how a negative silently stops pinning the
requirement it was written for.

Run either way:
    python3 scripts/art_creation_scan.py --selftest
    python3 scripts/test_art_creation_scan.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from art_creation_scan import DIGEST_STAGES, report, run_checks  # noqa: E402

BRIEF_TEXT = (
    "# Art brief\n## Readability brief\n## Art direction pillars\n"
    "## Palette and value structure\n## Shape language\n## Footprint grid\n"
    "## Material families\n## Camera\n"
)

BASE = {
    "brief": "brief.md", "brief_version": "3",
    "shape_rules": {"furniture": "orthogonal"},
    "stages": [{"name": "packed", "consumer": "src/loader.zig"}],
    "ledger": "ledger.json",
    "targets": ["native"],
    "captures": {"native": {"renderer": "title-own",
                            "contains_game_geometry": True,
                            "frame_sha256": "sha256:aa"}},
    "replication": {"present": True, "restore_exercised_at": "2026-01-01T00:00:00Z"},
    "artifact_dirs": [],
    "published_counts": {},
}

GOOD_ROW = {
    "id": "bed", "class": "furniture", "stage": "packed", "brief_ref": "art-brief@3",
    "prompt": "p", "seed": 1,
    "digests": {s: "sha256:x" for s in DIGEST_STAGES},
    "prep_stages": {"normal_repair": True},
    "fidelity": {"verdict": "accept", "rule": "orthogonal"},
    "measurement": {"name": "retained", "value": 1.0, "threshold": None},
    "rights": "unknown",
}

# (name, mutate(cfg, rows) -> (cfg, rows), want_exit, want_reqs)
CASES = [
    ("pass", lambda c, r: (c, r), 0, set()),
    ("no-capture", lambda c, r: (dict(c, captures={}), r), 1, {"art-draw-01"}),
    ("dcc-preview", lambda c, r: (
        dict(c, captures={"native": {"renderer": "dcc-preview",
                                     "contains_game_geometry": True,
                                     "frame_sha256": "s"}}), r), 1, {"art-draw-01"}),
    ("renderer-absent", lambda c, r: (
        dict(c, captures={"native": {"contains_game_geometry": True,
                                     "frame_sha256": "s"}}), r), 1, {"art-draw-01"}),
    ("renderer-blender-preview", lambda c, r: (
        dict(c, captures={"native": {"renderer": "blender-preview",
                                     "contains_game_geometry": True,
                                     "frame_sha256": "s"}}), r), 1, {"art-draw-01"}),
    ("clears-buffer-only", lambda c, r: (
        dict(c, captures={"native": {"renderer": "title-own",
                                     "contains_game_geometry": False,
                                     "frame_sha256": "s"}}), r), 1, {"art-draw-01"}),
    ("blank-rights", lambda c, r: (c, [dict(r[0], rights="")]), 1, {"art-rights-01"}),
    ("verdict-no-rule", lambda c, r: (
        c, [dict(r[0], fidelity={"verdict": "accept"})]), 1, {"art-accept-01"}),
    ("wrong-rule-for-class", lambda c, r: (
        c, [dict(r[0], fidelity={"verdict": "accept", "rule": "organic"})]),
        1, {"art-accept-01"}),
    ("meas-no-threshold", lambda c, r: (
        c, [dict(r[0], measurement={"name": "m", "value": 1.0})]), 1, {"art-accept-02"}),
    ("stage-empty", lambda c, r: (c, [dict(r[0], stage="")]),
        1, {"art-ledger-01", "art-done-01"}),
    ("stage-no-consumer", lambda c, r: (
        dict(c, stages=[{"name": "packed", "consumer": "none"}]), r), 1, {"art-stage-01"}),
    ("consumer-path-missing", lambda c, r: (
        dict(c, stages=[{"name": "packed", "consumer": "src/nowhere.zig"}]), r),
        1, {"art-stage-01"}),
    ("no-replication", lambda c, r: (
        dict(c, replication={"present": False}), r), 1, {"art-bytes-01"}),
    ("restore-never-run", lambda c, r: (
        dict(c, replication={"present": True}), r), 1, {"art-bytes-01"}),
    ("unversioned-brief", lambda c, r: (
        dict(c, brief_version=None), r), 1, {"art-brief-01"}),
    ("brief-version-substring", lambda c, r: (
        dict(c, brief_version="3"), [dict(r[0], brief_ref="art-brief@13")]),
        1, {"art-brief-01"}),
    ("no-shape-rule", lambda c, r: (
        dict(c, shape_rules={}), r), 1, {"art-brief-02"}),
    ("count-disagrees", lambda c, r: (
        dict(c, published_counts={"library": 99}), r), 1, {"art-ledger-01"}),
    ("count-unknown-label", lambda c, r: (
        dict(c, published_counts={"pieces": 4}), r), 1, {"art-ledger-01"}),
    # bool is a subclass of int and True == 1; 1.0 == 1 is also true. Both
    # look like the derived count and neither was ever derived as an integer.
    # These two are the false-pass the published-count check exists to close.
    ("count-bool", lambda c, r: (
        dict(c, published_counts={"library": True}), r), 1, {"art-ledger-01"}),
    ("count-float", lambda c, r: (
        dict(c, published_counts={"library": 1.0}), r), 1, {"art-ledger-01"}),
    ("count-string", lambda c, r: (
        dict(c, published_counts={"library": "1"}), r), 1, {"art-ledger-01"}),
    ("floor-fidelity-red", lambda c, r: (
        c, [dict(r[0], library_floor=1),
            dict(r[0], id="chair",
                 fidelity={"verdict": "reject", "rule": "orthogonal"})]),
        1, {"art-qty-01"}),
    ("accepted-not-terminal", lambda c, r: (
        dict(c, stages=[{"name": "prepared", "consumer": "src/loader.zig"},
                        {"name": "packed", "consumer": "src/loader.zig"}]),
        [dict(r[0], stage="prepared")]), 1, {"art-done-01"}),
]


def selftest() -> int:
    failed = 0
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "brief.md").write_text(BRIEF_TEXT, encoding="utf-8")
        (root / "src").mkdir()
        (root / "src" / "loader.zig").write_text("// loader\n", encoding="utf-8")
        for name, mutate, want, want_reqs in CASES:
            cfg, rows = mutate(dict(BASE), [dict(GOOD_ROW)])
            (root / "ledger.json").write_text(
                json.dumps({"assets": rows}), encoding="utf-8")
            findings = run_checks(cfg, root)
            got_fail = 1 if findings else 0
            got_reqs = {f.req for f in findings}
            if got_fail != want or got_reqs != want_reqs:
                failed += 1
                print(f"selftest FAIL {name}: expected exit {want} reqs "
                      f"{sorted(want_reqs) or '-'}, got exit {got_fail} reqs "
                      f"{sorted(got_reqs) or '-'}")
                for f in findings:
                    print("   ", f.line())
            else:
                print(f"selftest ok {name}  [{', '.join(sorted(got_reqs)) or '-'}]")
    # NOT_APPLICABLE must be exit 3, never 0.
    if report([], declared=False, counted=0) != 3:
        failed += 1
        print("selftest FAIL not-applicable exit code")
    print(f"selftest {'ok' if failed == 0 else 'FAIL'}: {len(CASES)} cases")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(selftest())
