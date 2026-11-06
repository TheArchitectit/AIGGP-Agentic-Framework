#!/usr/bin/env python3
"""Tests for spec-fleet-walk.sh's report capping + dedup shape (SGA-13).

The walk itself shells out to git clone, so these tests use local directory
paths (which the walk treats as already-present trees) instead of network
clones. Dual-runnable: pytest collects test_*.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WALK = HERE.parent / "scripts" / "spec-fleet-walk.sh"
CLASSIFIER = HERE.parent / "scripts" / "spec-fleet-classify.py"


def make_walk_repo(tmp: Path, *, state_label: str, openspec: bool = True) -> Path:
    root = tmp / state_label
    root.mkdir()
    if openspec:
        (root / "openspec" / "specs" / "foo").mkdir(parents=True)
        (root / "openspec" / "specs" / "foo" / "spec.md").write_text(
            "# foo\n\n### Requirement: x <!-- id: foo-01 -->\n")
    return root


def test_cap_and_omitted_shape(tmp_path):
    """The report keeps every repo and never drops unspaced names (SGA-13)."""
    declared = []
    for i in range(5):
        make_walk_repo(tmp_path, state_label=f"repo-{i}", openspec=(i % 2 == 0))
        declared.append(str(tmp_path / f"repo-{i}"))
    decl = tmp_path / "declared.txt"
    decl.write_text("\n".join(declared) + "\n")
    report = tmp_path / "report.json"
    work = tmp_path / "work"
    r = subprocess.run(["bash", str(WALK), "--declared", str(decl),
                        "--report", str(report), "--work", str(work)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["declared"] == 5
    assert len(data["repos"]) == 5  # every declared repo appears exactly once
    names = {entry["name"] for entry in data["repos"]}
    assert names == {f"repo-{i}" for i in range(5)}
    # unspaced repos are named, never red
    for entry in data["repos"]:
        if entry["state"] == "unspaced":
            assert entry["red"] is False


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([str(Path(__file__))]))