#!/usr/bin/env python3
# // spec: root-anchor-01, root-anchor-03
"""Python-scanner project-root anchoring — closes the ledger's OPEN item.

The three Node scanners (guardrails/semantic/run-tests) had their ancestor
walk-up removed and locked by tests/test_scanner_root_anchor.mjs. The 2026-09-20
audit's fresh-eyes pass found the identical defect class still present in the
Python scanners:

    scripts/regression_check.py  find_project_root(): walk up from Path.cwd()
                                 for package.json/Cargo.toml/.git/... — the
                                 same ancestor search root-anchor-01 forbids.
    scripts/scene_inventory.py    same walk-up, capped at 10 levels.
    scripts/failure_registry_check.py  _find_project_root(): walk up from
                                 Path.cwd() for the first .git, used to locate
                                 the consumer's overlay registry — and this one
                                 IS in the gate (ci.yml runs it).

Reproduced: from a standalone repo whose PARENT carries a marker, the
scanners resolve PROJECT_ROOT to the parent, not the repo — a scan that
believes it covers the project silently evaluates a foreign tree. regression_check.py
and failure_registry_check.py are both load-bearing (DevGate ci.yml, the
consumer drift template, deploy.sh), so this is not a dormant path.

This fixture pins the SAME contract for the Python side: root resolution is a
pure function of the scanner's own file location (the dir containing
.devgate/, else the checkout), shared by both scanners through one module,
never a marker walk-up and never process.cwd().

Run: python3 tests/test_python_root_anchor.py   (also pytest-discoverable)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

# Every module a scanner import pulls in as a sibling, so the synthetic repo is
# self-contained (mirrors the flat import bootstrap the real scripts use).
_PY_DEPS = [
    "regression_check.py",
    "scene_inventory.py",
    "failure_registry_check.py",
    "gate_overlay.py",
    "regression_audit.py",
    "regression_diff.py",
    "regression_sizes.py",
]

# The probe runs INSIDE the synthetic tree via subprocess, so the scanners are
# imported fresh from the copied scripts and their module-level PROJECT_ROOT
# reflects that tree — not this test process's cwd.
# getattr-with-sentinel, NOT a bare attribute read: scene_inventory has no
# module-level root yet (it resolves inside main()), and a crashing probe would
# report "probe crashed" instead of the honest pre-fix finding "S=MISSING".
_PROBE = """
import sys
sys.path.insert(0, {scripts!r})
import regression_check
import scene_inventory
import failure_registry_check  # guardrails-allow PREVENT-024: real DevGate scanner module (scripts/failure_registry_check.py), not an external package; comment is inert in the exec'd probe
print("R=" + str(getattr(regression_check, "PROJECT_ROOT", "MISSING")))
print("S=" + str(getattr(scene_inventory, "PROJECT_ROOT", "MISSING")))
print("F=" + str(getattr(failure_registry_check, "PROJECT_ROOT", "MISSING")))
"""


def _parse(out: str) -> dict[str, str]:
    vals: dict[str, str] = {}
    for line in out.splitlines():
        if line.startswith("R="):
            vals["regression"] = line[2:].strip()
        elif line.startswith("S="):
            vals["scene"] = line[2:].strip()
        elif line.startswith("F="):
            vals["failure_reg"] = line[2:].strip()
    return vals


def _copy_scripts(dest: Path) -> Path:
    scripts = dest / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "lib").mkdir(exist_ok=True)
    for name in _PY_DEPS:
        src = SCRIPTS / name
        if src.exists():
            (scripts / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    # The shared Python root contract (root-anchor-03) lives under scripts/lib
    # once it exists; copy the whole lib dir so the fixture stays valid against
    # both the pre-fix (import fails -> RED) and post-fix (import works) trees.
    lib_src = SCRIPTS / "lib"
    if lib_src.is_dir():
        for f in lib_src.iterdir():
            if f.suffix == ".py":
                (scripts / "lib" / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    return scripts


def _resolve_roots(scripts: Path, cwd: Path) -> dict[str, str]:
    res = subprocess.run(
        [sys.executable, "-c", _PROBE.format(scripts=str(scripts))],
        cwd=str(cwd),
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    assert res.returncode == 0, f"probe crashed: {res.stderr[:800]}"
    return _parse(res.stdout)


def _plant_marker(d: Path) -> None:
    (d / "package.json").write_text('{"name": "decoy-parent"}\n', encoding="utf-8")
    (d / ".git").mkdir(exist_ok=True)


def test_standalone_under_marker_parent(tmp_path):
    # <tmp>/parent carries markers; the repo <tmp>/parent/gameproj carries NONE.
    # The old walk-up settled on the parent. The layout contract must stay in
    # the repo regardless of cwd (invoked here from the repo).
    parent = tmp_path / "parent"
    repo = parent / "gameproj"
    scripts = _copy_scripts(repo)
    _plant_marker(parent)
    got = _resolve_roots(scripts, repo)
    assert got.get("regression") == str(repo), got
    assert got.get("scene") == str(repo), got
    assert got.get("failure_reg") == str(repo), got


def test_submodule_layout_resolves_to_consumer(tmp_path):
    # DevGate vendored at <consumer>/.devgate/ — root is the CONSUMER.
    consumer = tmp_path / "consumer"
    devgate = consumer / ".devgate"
    scripts = _copy_scripts(devgate)
    _plant_marker(consumer)
    got = _resolve_roots(scripts, consumer)
    assert got.get("regression") == str(consumer), got
    assert got.get("scene") == str(consumer), got
    assert got.get("failure_reg") == str(consumer), got


def test_root_is_independent_of_cwd(tmp_path):
    # A root anchored on __file__ must not move when cwd moves. The old
    # Path.cwd()-based code produced a different root per invocation dir —
    # exactly how it escaped to /mnt/data/git in the field.
    parent = tmp_path / "parent"
    repo = parent / "gameproj"
    scripts = _copy_scripts(repo)
    _plant_marker(parent)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "package.json").write_text('{"name": "unrelated"}\n', encoding="utf-8")
    a = _resolve_roots(scripts, repo)
    b = _resolve_roots(scripts, elsewhere)
    assert a.get("regression") == str(repo), a
    assert b.get("regression") == str(repo), f"root moved with cwd: {b}"
    assert a.get("scene") == str(repo), a
    assert b.get("scene") == str(repo), f"scene root moved with cwd: {b}"
    assert a.get("failure_reg") == str(repo), a
    assert b.get("failure_reg") == str(repo), f"failure-registry root moved with cwd: {b}"


def test_case_variant_dir_is_not_the_marker(tmp_path):
    # <proj>/.DevGate (mis-cased) is NOT the submodule marker; the scanner
    # installed there treats its own tree as the root, matching the Node
    # contract. Only the exact name ".devgate" triggers the parent hop.
    parent = tmp_path / "parent"
    proj = parent / "misconsumer"
    devgate = proj / ".DevGate"  # wrong casing on purpose
    scripts = _copy_scripts(devgate)
    _plant_marker(parent)
    got = _resolve_roots(scripts, proj)
    # Root must NOT hop to proj's parent for a mis-cased marker dir; the layout
    # contract sees basename != ".devgate" and keeps the .DevGate dir itself as
    # the standalone root.
    assert got.get("regression") == str(devgate), got
    assert got.get("scene") == str(devgate), got
    assert got.get("failure_reg") == str(devgate), got


def test_no_ancestor_walkup_survives(tmp_path):
    # Deepest escape reproduction: repo has no marker, MULTIPLE ancestors do.
    # A walk-up returns the nearest marked ancestor; the contract returns the
    # repo. This is the case the external audit proved with a real marker file.
    deep = tmp_path / "a" / "b"
    repo = deep / "repo"
    scripts = _copy_scripts(repo)
    _plant_marker(deep)
    _plant_marker(tmp_path / "a")
    got = _resolve_roots(scripts, repo)
    assert got.get("regression") == str(repo), got
    assert got.get("scene") == str(repo), got
    assert got.get("failure_reg") == str(repo), got


def test_shared_single_implementation():
    # root-anchor-03: both scanners import ONE shared module, not each their
    # own walkup. Assert the contract function is defined in exactly one file
    # under scripts/, and that neither scanner defines find_project_root.
    lib = SCRIPTS / "lib"
    shared = list(lib.glob("*.py")) if lib.is_dir() else []
    defining = [f for f in shared if "def project_root_for" in f.read_text(encoding="utf-8")]
    assert len(defining) == 1, f"expected one shared Python root module, found {defining}"
    # failure_registry_check is here because ci.yml actually invokes it, so it is
    # a scanner on the gate path like the other two, not an optional helper.
    # Both spellings must be checked: failure_registry_check's helper is
    # _find_project_root (leading underscore), and "def find_project_root" is NOT
    # a substring of "def _find_project_root" — checking one spelling would let
    # the other's walk-up survive this gate silently.
    for scanner in ("regression_check.py", "scene_inventory.py", "failure_registry_check.py"):
        text = (SCRIPTS / scanner).read_text(encoding="utf-8")
        # Check for a DEFINITION, not the substring: the migration comments in
        # both files still name find_project_root() to explain what was removed,
        # and a bare substring assert would match its own documentation.
        for name in ("def find_project_root", "def _find_project_root"):
            assert name not in text, f"{scanner} still defines its own walk-up ({name})"
        assert "project_root_for" in text, f"{scanner} does not use the shared contract"


def test_contract_is_pure_function():
    # Mirror of the Node check: the shared contract resolves from the path
    # string alone and never touches the filesystem (a marker-based impl can't
    # pass a probe on a nonexistent path).
    lib = SCRIPTS / "lib"
    shared = [f for f in lib.glob("*.py") if "def project_root_for" in f.read_text(encoding="utf-8")]
    assert shared, "no shared contract module to probe"
    mod = shared[0].stem
    probe = (
        f"import sys; sys.path.insert(0, {str(lib)!r}); sys.path.insert(0, {str(SCRIPTS)!r})\n"
        f"import {mod}\n"
        f"f = {mod}.project_root_for\n"
        "print(f('/x/.devgate'))\n"
        "print(f('/nonexistent-aaa/bbb'))\n"
    )
    res = subprocess.run([sys.executable, "-c", probe], capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    assert res.returncode == 0, res.stderr[:800]
    lines = res.stdout.split()
    # '/x/.devgate' -> '/x' (marker name stripped); never consulted the disk.
    # Compare as PATHS, not strings: on Windows the contract correctly returns
    # '\x', so asserting the literal "/x" is asserting a POSIX separator rather
    # than the behaviour.
    assert Path(lines[0]) == Path("/x"), lines
    assert Path(lines[1]) == Path("/nonexistent-aaa/bbb"), lines


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
