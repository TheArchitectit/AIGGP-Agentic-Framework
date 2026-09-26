#!/usr/bin/env python3
"""Fixture tests for silent-success-scan.sh's project-overlay + exclude_globs
resolution — the gate_overlay.py merge contract applied to the silent-success
family list, so a project can scope/retune a family WITHOUT editing the
submodule baseline (owner directive 2026-09-22: repo-local rule data, fleet
baseline untouched).

The contract these lock in:
  * NO overlay -> baseline-only behaviour (every consumer that has not adopted
    an overlay is byte-identical unaffected — this is the fleet-safety
    guarantee the merge must never regress).
  * overlay present -> entries MERGE by "family" id, overlay wins on collision
    (replaced in the bundled position), new families append.
  * exclude_globs skips matching files for THAT family only — and the same
    marker in a non-excluded file still FAILS (an exclusion is a scope change,
    not a family mute).
  * a family's exclusion does not blind OTHER enabled families to the same
    file (the second enabled family still reports its marker there).
  * a malformed overlay FAILS CLOSED — falling back to the baseline would
    quietly drop the project's own rules.

The tests exec the real scan script (bash + python heredoc), so they lock the
shell/python wiring, not just a helper.

Runnable two ways (run-tests.mjs discovers test_*.py via pytest, and this file
also works standalone with plain asserts):

    python3 tests/test_silent_success_overlay.py
    pytest tests/test_silent_success_overlay.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

# Requires Unix tooling (bash/chmod/fcntl/systemctl/podman): these tests
# shell out to things that do not exist on Windows, so they cannot run there.
# A test that cannot run must SKIP, not fail -- failing here is indistinguishable
# from real breakage.
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="requires Unix tooling")

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "silent-success-scan.sh"
RULES_REL = ".guardrails/prevention-rules/silent-success-rules.json"
ALLOWLIST_REL = ".guardrails/silent-success-allowlist.json"


def _family(name: str, regex: str, *, enabled: bool, file_glob, exclude=None) -> dict:
    rule = {
        "family": name,
        "regex": regex,
        "file_glob": list(file_glob),
        "enabled": enabled,
        "language": "fixture",
        "note": "fixture rule",
    }
    if exclude:
        rule["exclude_globs"] = list(exclude)
    return rule


def _rules(*families) -> dict:
    return {"rules": [f for f in families]}


def _mk_project(tmp: Path, *, bundled_rules: dict, overlay_rules: dict | None,
                allowlist_entries=(), files: dict[str, str]) -> Path:
    """Build <tmp>/.devgate (submodule: scan scripts + baseline config) and the
    project source tree. A project .git file marks the parent as the scan
    root (the scan derives project_root from it)."""
    dg = tmp / ".devgate"
    (dg / "scripts").mkdir(parents=True)
    (tmp / ".git").write_text("gitdir: .devgate\n", encoding="utf-8")
    (dg / RULES_REL).parent.mkdir(parents=True, exist_ok=True)
    (dg / RULES_REL).write_text(json.dumps(bundled_rules), encoding="utf-8")
    (dg / ALLOWLIST_REL).parent.mkdir(parents=True, exist_ok=True)
    (dg / ALLOWLIST_REL).write_text(
        json.dumps({"entries": list(allowlist_entries)}), encoding="utf-8")
    # The scope contract is a load-bearing dependency of the scan script
    # (fw-scope-01): the fixture sandbox must carry it like a real
    # submodule does.
    (dg / ".guardrails").mkdir(parents=True, exist_ok=True)
    (dg / ".guardrails" / "scope.json").write_text(
        (REPO_ROOT / ".guardrails" / "scope.json").read_text(encoding="utf-8"),
        encoding="utf-8")
    # copy the script + its one import (gate_overlay.py) into the fixture root
    for name in ("silent-success-scan.sh", "gate_overlay.py"):
        (dg / "scripts" / name).write_text(
            (REPO_ROOT / "scripts" / name).read_text(encoding="utf-8"), encoding="utf-8")
    if overlay_rules is not None:
        target = tmp / RULES_REL
        target.parent.mkdir(parents=True, exist_ok=True)
        if overlay_rules == "RAW":
            target.write_text("{not json", encoding="utf-8")
        else:
            target.write_text(json.dumps(overlay_rules), encoding="utf-8")
    for rel, text in files.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp


def _run(tmp: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(tmp / ".devgate" / "scripts" / "silent-success-scan.sh")],
        cwd=tmp, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)


GO_CLOSE = _family("go_close", r"_\s*=\s*f\.Close\(\)", enabled=True, file_glob=["*.go"])
PY_PASS = _family("py_pass", r"^\s*pass\s+#\s*TODO", enabled=True, file_glob=["*.py"])


def _out(p: subprocess.CompletedProcess) -> str:
    return p.stdout + p.stderr


def test_no_overlay_is_baseline_only():
    with tempfile.TemporaryDirectory() as d:
        tmp = _mk_project(Path(d),
                          bundled_rules=_rules(GO_CLOSE), overlay_rules=None,
                          files={"a.go": "_ = f.Close()\n"})
        p = _run(tmp)
        assert p.returncode == 1, f"unlisted marker must fail, got: {_out(p)}"
        assert "a.go:1 (go_close)" in _out(p), _out(p)
        assert "overlay merged" not in _out(p), "no overlay -> no merge line"
        assert "[excluded]" not in _out(p)


def test_overlay_replaces_same_family_adds_new():
    with tempfile.TemporaryDirectory() as d:
        new_go = _family("go_close", r"_\s*=\s*f\.Close\(\)", enabled=True,
                         file_glob=["*.go"], exclude=["*_test.go"])
        extra = _family("ts_todo", r"TODO", enabled=False, file_glob=["*.ts"])
        tmp = _mk_project(Path(d),
                          bundled_rules=_rules(GO_CLOSE),
                          overlay_rules=_rules(new_go, extra),
                          files={"pkg/x_test.go": "_ = f.Close()\n",
                                 "pkg/x.go": "_ = f.Close()\n"})
        p = _run(tmp)
        out = _out(p)
        assert p.returncode == 1, f"non-test marker must still fail: {out}"
        assert "overlay merged" in out, out
        # replaced in the bundled position, new family appended: 2 in effect
        assert "2 family(ies) in effect" in out, out
        assert "pkg/x.go:1 (go_close)" in out, f"non-test hit unreported: {out}"
        # the appended family is enabled:false -> contributes nothing
        assert " (ts_todo)" not in out, out


def test_exclude_globs_scopes_not_mutes():
    with tempfile.TemporaryDirectory() as d:
        new_go = _family("go_close", r"_\s*=\s*f\.Close\(\)", enabled=True,
                         file_glob=["*.go"], exclude=["*_test.go"])
        tmp = _mk_project(Path(d),
                          bundled_rules=_rules(GO_CLOSE),
                          overlay_rules=_rules(new_go),
                          files={"a_test.go": "_ = f.Close()\n",
                                 "a.go": "_ = f.Close()\n"})
        p = _run(tmp)
        out = _out(p)
        assert p.returncode == 1, f"the non-test file must still fail: {out}"
        assert "  [excluded] a_test.go:1 (go_close)" in out, \
            f"excluded hit must report as [excluded]: {out}"
        assert "  [NEW/unlisted] a.go:1 (go_close)" in out, \
            f"exclusion leaked to non-test file: {out}"


def test_exclusion_is_per_family_not_whole_file():
    with tempfile.TemporaryDirectory() as d:
        py = _family("go_py", r"_\s*=\s*f\.Close\(\)", enabled=True, file_glob=["*"])
        new_go = _family("go_close", r"_\s*=\s*f\.Close\(\)", enabled=True,
                         file_glob=["*.go"], exclude=["*_test.go"])
        tmp = _mk_project(Path(d),
                          bundled_rules=_rules(py), overlay_rules=_rules(new_go),
                          files={"z_test.go": "_ = f.Close()\n"})
        p = _run(tmp)
        out = _out(p)
        assert p.returncode == 1, f"other families must still scan the file: {out}"
        assert "z_test.go:1 (go_close)" in out, f"own family's exclusion missing: {out}"
        assert "z_test.go:1 (go_py)" in out, f"per-file mute leaked: {out}"


def test_malformed_overlay_fails_closed():
    with tempfile.TemporaryDirectory() as d:
        tmp = _mk_project(Path(d),
                          bundled_rules=_rules(GO_CLOSE), overlay_rules="RAW",
                          files={"a.go": "_ = f.Close()\n"})
        p = _run(tmp)
        out = _out(p)
        assert p.returncode == 1, f"malformed overlay must fail closed: {out}"
        assert "overlay" in out.lower(), f"error must name the overlay: {out}"
        # fail CLOSED, not silently ignored: the baseline scan result must not
        # masquerade as a merge success
        assert "overlay merged" not in out


def test_standalone_checkout_same_path_guard():
    # devgate_root == project_root: the overlay file IS the baseline file.
    # Must not double-count, must not error, behaviour == baseline-only.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / RULES_REL).parent.mkdir(parents=True)
        (tmp / RULES_REL).write_text(json.dumps(_rules(GO_CLOSE)), encoding="utf-8")
        (tmp / ALLOWLIST_REL).write_text(json.dumps({"entries": []}), encoding="utf-8")
        (tmp / "scripts").mkdir()
        for name in ("silent-success-scan.sh", "gate_overlay.py"):
            (tmp / "scripts" / name).write_text(
                (REPO_ROOT / "scripts" / name).read_text(encoding="utf-8"), encoding="utf-8")
        (tmp / ".guardrails" / "scope.json").parent.mkdir(parents=True, exist_ok=True)
        (tmp / ".guardrails" / "scope.json").write_text(
            (REPO_ROOT / ".guardrails" / "scope.json").read_text(encoding="utf-8"),
            encoding="utf-8")
        (tmp / "a.go").write_text("_ = f.Close()\n", encoding="utf-8")
        p = subprocess.run(["bash", str(tmp / "scripts" / "silent-success-scan.sh")],
                           cwd=tmp, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        out = _out(p)
        assert p.returncode == 1, out
        assert "a.go:1 (go_close)" in out, out
        assert "overlay merged" not in out, \
            f"same-path file must not be merged with itself: {out}"


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
