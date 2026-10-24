#!/usr/bin/env python3
"""Tests for scripts/check_boundary.py — the fleet-manager boundary gate.

Planted violations, one per exit-code path, plus the direction that must NOT
red (boundary -> core) and the exempt-list pin that keeps the gate from
quietly growing a hole. Dual-runnable: pytest collects test_*.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
GATE = REPO / "scripts" / "check_boundary.py"

MANIFEST = {
    "schema": "devgate-fleet-manager-boundary/1",
    "boundary_root": "fleet-manager",
    "license": {"spdx": "BSD-3-Clause", "file": "LICENSE",
                "separate_grant": False},
    "paths": ["fleet-manager/README.md", "fleet-manager/manifest.json",
              "fleet-manager/contracts/v1/**", "fleet-manager/tests/**"],
    "forbidden_roots": ["enterprise"],
    "exempt_paths": ["scripts/check_boundary.py"],
}


def make_repo(tmp: Path, manifest: dict | None = None) -> Path:
    """A minimal tree the gate accepts: .git, manifest, declared files."""
    root = tmp / "repo"
    (root / ".git").mkdir(parents=True)
    (root / "fleet-manager").mkdir()
    (root / "fleet-manager" / "README.md").write_text("# boundary\n")
    (root / "fleet-manager" / "manifest.json").write_text(
        json.dumps(manifest if manifest is not None else MANIFEST))
    (root / "hub").mkdir()
    (root / "hub" / "core.py").write_text("print('core')\n")
    return root


def run_gate(root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), "--repo", str(root), *extra],
        capture_output=True, text=True, timeout=120)


def test_clean_tree_exits_zero(tmp_path):
    res = run_gate(make_repo(tmp_path))
    assert res.returncode == 0, res.stderr
    assert "[boundary] OK" in res.stdout


def test_core_importing_the_boundary_is_a_violation(tmp_path):
    root = make_repo(tmp_path)
    (root / "hub" / "leaky.py").write_text(
        "from fleet_manager.domain import pool\n")
    res = run_gate(root)
    assert res.returncode == 1
    assert "hub/leaky.py:1" in res.stderr


def test_core_naming_a_boundary_path_is_a_violation(tmp_path):
    root = make_repo(tmp_path)
    (root / "scripts").mkdir()
    (root / "scripts" / "loader.sh").write_text(
        'python3 "$ROOT/fleet-manager/tool.py"\n')
    res = run_gate(root)
    assert res.returncode == 1
    assert "scripts/loader.sh:1" in res.stderr


def test_boundary_importing_core_is_allowed(tmp_path):
    """The direction the design allows must not red."""
    root = make_repo(tmp_path)
    (root / "fleet-manager" / "tests").mkdir()
    (root / "fleet-manager" / "tests" / "test_pool.py").write_text(
        "from hub.core import thing\n")
    res = run_gate(root)
    assert res.returncode == 0, res.stderr


def test_undeclared_file_under_the_boundary_is_a_violation(tmp_path):
    root = make_repo(tmp_path)
    (root / "fleet-manager" / "api").mkdir()
    (root / "fleet-manager" / "api" / "server.py").write_text("x = 1\n")
    res = run_gate(root)
    assert res.returncode == 1
    assert "fleet-manager/api/server.py" in res.stderr


def test_declared_glob_covers_a_nested_contract(tmp_path):
    root = make_repo(tmp_path)
    (root / "fleet-manager" / "contracts" / "v1").mkdir(parents=True)
    (root / "fleet-manager" / "contracts" / "v1" / "pool.json").write_text("{}\n")
    res = run_gate(root)
    assert res.returncode == 0, res.stderr


def test_malformed_manifest_exits_two_not_clean(tmp_path):
    root = make_repo(tmp_path)
    (root / "fleet-manager" / "manifest.json").write_text("{not json")
    res = run_gate(root)
    assert res.returncode == 2
    assert "not JSON" in res.stderr


def test_separate_license_grant_exits_two(tmp_path):
    """OD-001: Phase 1 ships BSD 3-Clause with no separate grant."""
    bad = dict(MANIFEST)
    bad["license"] = {"spdx": "BSD-3-Clause", "file": "LICENSE",
                      "separate_grant": True}
    res = run_gate(make_repo(tmp_path, bad))
    assert res.returncode == 2
    assert "separate license grant" in res.stderr


def test_manifest_path_outside_the_root_exits_two(tmp_path):
    bad = dict(MANIFEST)
    bad["paths"] = ["fleet-manager/README.md", "hub/everything/**"]
    res = run_gate(make_repo(tmp_path, bad))
    assert res.returncode == 2
    assert "not inside the boundary root" in res.stderr


def test_prose_may_name_the_boundary(tmp_path):
    """Documentation is not a dependency edge (the gate must not red on prose)."""
    root = make_repo(tmp_path)
    (root / "docs").mkdir()
    (root / "docs" / "note.md").write_text(
        "Product-tiers code lives under fleet-manager/ only.\n")
    res = run_gate(root)
    assert res.returncode == 0, res.stderr


def test_changed_path_in_a_forbidden_root_is_a_violation(tmp_path):
    root = make_repo(tmp_path)
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t",
                    "-c", "user.email=t@example.invalid", "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t",
                    "-c", "user.email=t@example.invalid", "commit", "-qm", "base"],
                   check=True)
    subprocess.run(["git", "-C", str(root), "checkout", "-q", "-b", "work"],
                   check=True)
    (root / "enterprise").mkdir()
    (root / "enterprise" / "billing.py").write_text("x = 1\n")
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t",
                    "-c", "user.email=t@example.invalid", "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t",
                    "-c", "user.email=t@example.invalid", "commit", "-qm", "leak"],
                   check=True)
    res = run_gate(root, "--changed-base", "main")
    assert res.returncode == 1
    assert "enterprise/billing.py" in res.stderr


def test_exempt_list_is_pinned_to_the_gate_and_its_test():
    """The exempt list is the gate's only hole; it must not grow quietly."""
    manifest = json.loads(
        (REPO / "fleet-manager" / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["exempt_paths"]) == {
        "scripts/check_boundary.py", "tests/test_check_boundary.py"}
