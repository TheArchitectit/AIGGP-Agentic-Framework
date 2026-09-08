#!/usr/bin/env python3
"""Fixture tests for gate_overlay.py — the bundled-baseline + project-overlay
merge behind the submodule layout.

The contract these lock in (and the regressions each one prevents):
  * NO overlay -> bundled baseline only (byte-identical behaviour to before the
    merge existed; every game that hasn't adopted an overlay is unaffected).
  * overlay present -> entries MERGE, not replace. A game adding its own rules
    must not silently drop upstream's, and must not fork them into its repo.
  * same id -> the OVERLAY entry wins, in the bundled position (retune severity,
    fix a false positive), and the count stays the same (no duplicate report).
  * explicit path -> SINGLE source, no merge ("I told you exactly what to read").
  * JSONL failure registry merges by failure_id the same way.
  * _source provenance tags survive the merge so the git-owning repo can be
    resolved per entry.

Runnable two ways (pytest collects the test_* functions; the __main__ block runs
them with plain asserts):

    python3 tests/test_gate_overlay.py
    pytest tests/test_gate_overlay.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import gate_overlay  # noqa: E402


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj) if not isinstance(obj, str) else obj)


def _rules_payload(ids):
    return {"rules": [{"rule_id": i, "enabled": True, "pattern": "x", "severity": "error",
                       "message": i, "file_glob": ["*.go"]} for i in ids]}


def _proj(tmp: Path, overlay_rules=None, bundled_rules=None, semantic_bundled=None, semantic_overlay=None):
    """Build a <tmp>/.devgate + <tmp>/ project pair with chosen rule sets."""
    dg = tmp / ".devgate"
    dgr = dg / ".guardrails" / "prevention-rules"
    pgr = tmp / ".guardrails" / "prevention-rules"
    _write(dgr / "pattern-rules.json", bundled_rules if bundled_rules is not None else _rules_payload(["PREVENT-A", "PREVENT-B"]))
    if semantic_bundled is not None:
        _write(dgr / "semantic-rules.json", semantic_bundled)
    if overlay_rules is not None:
        _write(pgr / "pattern-rules.json", overlay_rules)
    if semantic_overlay is not None:
        _write(pgr / "semantic-rules.json", semantic_overlay)
    return dg, tmp


def test_no_overlay_is_baseline_only():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        # point gate_overlay's devgate_root() at our fake by monkeypatching
        gate_overlay.devgate_root = lambda: tmp / ".devgate"
        _proj(tmp)
        rules = gate_overlay.resolve_rules(tmp)
        ids = [r["rule_id"] for r in rules]
        assert ids == ["PREVENT-A", "PREVENT-B"], ids
        assert all(r["_source"] == "devgate" for r in rules), "baseline tagged devgate"


def test_overlay_appends_new_ids():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        gate_overlay.devgate_root = lambda: tmp / ".devgate"
        _proj(tmp, overlay_rules=_rules_payload(["PREVENT-XI-001"]))
        ids = [r["rule_id"] for r in gate_overlay.resolve_rules(tmp)]
        assert "PREVENT-XI-001" in ids and "PREVENT-A" in ids, ids
        assert len(ids) == 3, f"merge, not replace: {ids}"


def test_overlay_replaces_same_id_in_place():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        gate_overlay.devgate_root = lambda: tmp / ".devgate"
        over = _rules_payload(["PREVENT-B"])
        over["rules"][0]["severity"] = "warning"  # retune
        over["rules"][0]["message"] = "retuned"
        _proj(tmp, overlay_rules=over)
        rules = {r["rule_id"]: r for r in gate_overlay.resolve_rules(tmp)}
        assert len(rules) == 2, "same-id replace keeps the count (no duplicate)"
        assert rules["PREVENT-B"]["message"] == "retuned", "overlay entry won"
        assert rules["PREVENT-B"]["_source"] == "project", "provenance is the overlay"
        # order preserved: PREVENT-B stays in position 1 (where it was in bundled)
        ordered = [r["rule_id"] for r in gate_overlay.resolve_rules(tmp)]
        assert ordered == ["PREVENT-A", "PREVENT-B"], ordered


def test_explicit_path_is_single_source_no_merge():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        gate_overlay.devgate_root = lambda: tmp / ".devgate"
        over_dir = tmp / ".guardrails" / "prevention-rules"
        _proj(tmp, overlay_rules=_rules_payload(["ONLY-OVERLAY"]))
        rules = gate_overlay.resolve_rules(tmp, explicit=over_dir)
        ids = [r["rule_id"] for r in rules]
        assert ids == ["ONLY-OVERLAY"], f"explicit path must not merge baseline: {ids}"


def test_semantic_rules_merged_with_pattern_rules():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        gate_overlay.devgate_root = lambda: tmp / ".devgate"
        _proj(tmp,
              overlay_rules=_rules_payload(["PREVENT-X"]),
              semantic_bundled=_rules_payload(["SEMANTIC-001"]),
              semantic_overlay=_rules_payload(["SEMANTIC-SI-001"]))
        rules = gate_overlay.resolve_rules(tmp)
        kinds = {r["rule_id"]: r["_kind"] for r in rules}
        assert kinds["PREVENT-A"] == "pattern" and kinds["SEMANTIC-001"] == "semantic", kinds
        ids = [r["rule_id"] for r in rules]
        for want in ["PREVENT-A", "PREVENT-X", "SEMANTIC-001", "SEMANTIC-SI-001"]:
            assert want in ids, f"{want} missing from merged {ids}"


def test_registry_merges_by_failure_id():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        dg = tmp / ".devgate"
        gate_overlay.devgate_root = lambda: dg
        def line(fid, status="active"):
            return json.dumps({"failure_id": fid, "status": status, "fix_commit": "pending",
                               "category": "bug", "severity": "high", "error_message": fid,
                               "root_cause": "x", "affected_files": [], "regression_pattern": "y",
                               "prevention_rule": "z", "timestamp": "2026-01-01T00:00:00Z"})
        _write(dg / ".guardrails" / "failure-registry.jsonl", line("FAIL-base1") + "\n")
        _write(tmp / ".guardrails" / "failure-registry.jsonl",
               line("FAIL-proj1") + "\n" + line("FAIL-base1", status="deprecated") + "\n")
        entries, owner = gate_overlay.resolve_registry(tmp)
        ids = {e["failure_id"] for e in entries}
        assert ids == {"FAIL-base1", "FAIL-proj1"}, ids
        by_id = {e["failure_id"]: e for e in entries}
        assert by_id["FAIL-base1"]["status"] == "deprecated", "overlay replaced the baseline entry"
        # A REPLACED entry is owned by whoever wrote the winning copy — its
        # fix_commit must validate against the overlay's repo, not upstream's.
        assert owner["FAIL-base1"] == tmp, "replaced entry re-points git at the overlay repo"
        assert owner["FAIL-proj1"] == tmp, "project-owned entry points git at the project"


def test_registry_status_filter():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        dg = tmp / ".devgate"
        gate_overlay.devgate_root = lambda: dg
        def line(fid, status):
            return json.dumps({"failure_id": fid, "status": status})
        _write(dg / ".guardrails" / "failure-registry.jsonl",
               line("A", "active") + "\n" + line("R", "resolved") + "\n" + line("D", "deprecated") + "\n")
        all_e, _ = gate_overlay.resolve_registry(tmp)
        assert {e["failure_id"] for e in all_e} == {"A", "R", "D"}, "no filter returns all"
        scanned, _ = gate_overlay.resolve_registry(tmp, statuses=("active", "resolved"))
        assert {e["failure_id"] for e in scanned} == {"A", "R"}, "SCANNED_STATUSES filter applied"


def _run_all() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ok   {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
