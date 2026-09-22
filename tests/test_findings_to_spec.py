#!/usr/bin/env python3
"""Tests for findings_to_spec.py — the gate-findings -> openspec scaffolder.

Contract being locked in:
  * every merged-registry finding becomes a requirement block with a kebab-case
    `<!-- id: ... -->` the traceability gate (spec_traceability.REQ_ID) can parse
  * running TWICE appends NOTHING the second time (idempotent) — the loop is
    "run gates, re-scaffold" and must not duplicate requirements each cycle
  * a NEW finding after the first run is appended; existing content survives
  * `// spec: <id>` in a source file flips that requirement to covered
  * --stdin folds live scanner violations in, deduped per rule+file
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "findings_to_spec.py"

sys.path.insert(0, str(HERE.parent / "scripts"))
import spec_traceability  # noqa: E402  (share the gate's regexes — the point is compatibility)


def _entry(fid, category="save", severity="warning", msg="a known bug", **kw):
    d = {"failure_id": fid, "category": category, "severity": severity,
         "error_message": msg, "status": "active",
         "root_cause": "because", "affected_files": [f"src/{category}.rs"]}
    d.update(kw)
    return json.dumps(d)


def _root(tmp: Path, entries):
    reg = tmp / ".guardrails" / "failure-registry.jsonl"
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text("\n".join(entries) + "\n", encoding="utf-8")
    return tmp


def _run(root: Path, *args):
    reg = root / ".guardrails" / "failure-registry.jsonl"
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root),
                           "--registry", str(reg), *args],
                          capture_output=True, text=True)


def test_generates_traceable_ids(tmp_path=None):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = _root(Path(d), [_entry("FAIL-SI-001"), _entry("FAIL-SI-002")])
        r = _run(root, "--capability", "save-system")
        assert r.returncode == 0, r.stderr
        spec = root / "openspec" / "specs" / "save-system" / "spec.md"
        assert spec.exists(), "spec.md not written"
        ids = spec_traceability.REQ_ID.findall(spec.read_text())
        assert len(ids) == 2, ids
        # every generated id must be kebab-case so the gate can parse it back
        for i in ids:
            assert re.fullmatch(r"[a-z0-9][a-z0-9-]*", i), i


def test_second_run_is_idempotent(tmp_path=None):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = _root(Path(d), [_entry("FAIL-A"), _entry("FAIL-B")])
        _run(root, "--capability", "gen")
        first = (root / "openspec" / "specs" / "gen" / "spec.md").read_text()
        r2 = _run(root, "--capability", "gen")
        second = (root / "openspec" / "specs" / "gen" / "spec.md").read_text()
        assert first == second, "second run must not change the spec"
        assert "in sync" in r2.stdout, r2.stdout


def test_new_finding_appends_existing_survives(tmp_path=None):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = _root(Path(d), [_entry("FAIL-A")])
        _run(root, "--capability", "gen")
        spec = root / "openspec" / "specs" / "gen" / "spec.md"
        before = spec.read_text()
        spec.write_text(before + "\n<!-- human note: keep me -->\n")
        # add a second finding
        (root / ".guardrails" / "failure-registry.jsonl").write_text(
            _entry("FAIL-A") + "\n" + _entry("FAIL-Z") + "\n", encoding="utf-8")
        _run(root, "--capability", "gen")
        after = spec.read_text()
        assert "keep me" in after, "hand edit must survive"
        assert len(spec_traceability.REQ_ID.findall(after)) == 2, after


def test_marker_makes_it_covered(tmp_path=None):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = _root(Path(d), [_entry("FAIL-SI-009")])
        _run(root, "--capability", "combat")
        spec = root / "openspec" / "specs" / "combat" / "spec.md"
        rid = spec_traceability.REQ_ID.findall(spec.read_text())[0]
        (root / "src" ).mkdir(exist_ok=True)
        (root / "src" / "combat.rs").write_text(f"// spec: {rid}\nfn x() {{}}\n")
        tr = subprocess.run([sys.executable, str(HERE.parent / "scripts" / "spec_traceability.py"),
                             "--root", str(root), "--report"], capture_output=True, text=True)
        assert f"{rid}: covered" in tr.stdout, tr.stdout


def test_stdin_scanner_findings_deduped(tmp_path=None):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = _root(Path(d), [])  # no registry findings
        scan = (
            "[GUARDRAILS][warning] PREVENT-SI-002 src/save_load.rs:55 — serialization swallows\n"
            "[GUARDRAILS][warning] PREVENT-SI-002 src/save_load.rs:63 — serialization swallows\n"
        )
        r = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root),
                            "--registry", str(root / ".guardrails" / "failure-registry.jsonl"),
                            "--stdin", "--capability", "save"],
                           input=scan, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        spec = root / "openspec" / "specs" / "save" / "spec.md"
        assert spec.exists()
        # same rule+file across two lines -> ONE requirement
        assert len(spec_traceability.REQ_ID.findall(spec.read_text())) == 1, spec.read_text()


def _run_all() -> int:
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ok   {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
