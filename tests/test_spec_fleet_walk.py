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


def test_capped_summary_lists_and_omitted_counts(tmp_path):
    """unspaced[] / invalid[] / gaps_top[] are capped at 40 with omitted counts."""
    declared = []
    for i in range(45):
        make_walk_repo(tmp_path, state_label=f"unspaced-{i:03d}", openspec=False)
        declared.append(str(tmp_path / f"unspaced-{i:03d}"))
    decl = tmp_path / "declared.txt"
    decl.write_text("\n".join(declared) + "\n")
    report = tmp_path / "report.json"
    r = subprocess.run(["bash", str(WALK), "--declared", str(decl),
                        "--report", str(report), "--work", str(tmp_path / "work")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    data = json.loads(report.read_text(encoding="utf-8"))
    # the full list is never truncated...
    assert data["declared"] == 45
    assert len(data["repos"]) == 45
    # ...and the summary lists are capped at 40 with the remainder counted
    assert len(data["unspaced"]) == 40
    assert data["unspaced_omitted"] == 5
    assert data["unspaced"][0]["name"] == "unspaced-000"
    assert isinstance(data["invalid"], list)
    assert isinstance(data["gaps_top"], list)


def test_provenance_findings_travel_with_the_row(tmp_path):
    """A drift finding must reach the report, or the sweep reads clean forever.

    The workflow's provenance step reads `provenance` off each report row; a
    row that drops it makes every nightly say "provenance: clean" while the
    templates drift. Pin the field, the drift list, and the red flag.
    """
    root = tmp_path / "repo"
    root.mkdir()
    (root / "templates" / "openspec").mkdir(parents=True)
    vendored = root / "templates" / "openspec" / "spec.md"
    vendored.write_text("# local copy that no longer matches the pin\n")
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({"templates": {"openspec-spec": {
        "source": None,
        "pinned_sha256": "0" * 64,
        "vendored_path": "templates/openspec/spec.md",
    }}}))
    decl = tmp_path / "declared.txt"
    decl.write_text(str(root) + "\n")
    report = tmp_path / "report.json"
    r = subprocess.run(["bash", str(WALK), "--declared", str(decl),
                        "--report", str(report), "--work", str(tmp_path / "work"),
                        "--lock-file", str(lock)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    row = json.loads(report.read_text(encoding="utf-8"))["repos"][0]
    prov = row["provenance"]
    assert [d["kind"] for d in prov["drift"]] == ["local"]
    # findings travel, and they are findings (issue), not red (SGA-21 vs 22)
    assert row["provenance_findings"] is True
    assert row["provenance_red"] is False


def test_lock_provenance_is_checked_once_not_per_repo(tmp_path):
    """Pin-integrity is a property of the lock, not of every scanned tree."""
    content = tmp_path / "upstream.md"
    content.write_text("# upstream copy\n")
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({"templates": {"openspec-spec": {
        "source": None,
        "pin_source": content.as_uri(),
        "pinned_sha256": "2" * 64,
        "vendored_path": None,
    }}}))
    declared = []
    for i in range(3):
        root = tmp_path / f"repo-{i}"
        root.mkdir()
        declared.append(str(root))
    decl = tmp_path / "declared.txt"
    decl.write_text("\n".join(declared) + "\n")
    report = tmp_path / "report.json"
    r = subprocess.run(["bash", str(WALK), "--declared", str(decl),
                        "--report", str(report), "--work", str(tmp_path / "work"),
                        "--lock-file", str(lock)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["lock_provenance"]["fault"] is True
    for row in data["repos"]:
        assert not (row.get("provenance") or {}).get("fault")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([str(Path(__file__))]))