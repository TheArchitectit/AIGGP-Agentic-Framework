#!/usr/bin/env python3
"""Tests for the spec intake gate classifier (SGA-10..15, SGA-20..22).

Dual-runnable: pytest collects test_*; `python3 tests/...` runs them too.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLASSIFIER = HERE.parent / "scripts" / "spec-fleet-classify.py"
PYTHON = sys.executable


def run(*argv, env=None):
    return subprocess.run([PYTHON, str(CLASSIFIER), *argv],
                         capture_output=True, text=True, env=env)


def make_repo(tmp_path: Path, *, openspec: bool = True) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    if openspec:
        (root / "openspec" / "specs" / "foo").mkdir(parents=True)
        (root / "openspec" / "specs" / "foo" / "spec.md").write_text(
            "# foo\n\n## Purpose\n\nA capability for testing.\n\n## Requirements\n\n### Requirement: x\n<!-- id: foo-01 -->\nThe system shall do x.\n\n#### Scenario: the condition\n- **WHEN** the condition holds\n- **THEN** the outcome happens\n")
    return root


def test_unspaced_never_red(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()  # no openspec material
    tier = tmp_path / "tier.txt"
    tier.write_text("")
    r = run("--root", str(root), "--tier-file", str(tier),
            "--repo-name", "owner/repo", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    cls = data["classification"]
    assert cls["state"] == "unspaced"
    assert cls["red"] is False


def test_tiered_invalid_is_red(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "openspec" / "specs" / "foo").mkdir(parents=True)
    (root / "openspec" / "specs" / "foo" / "spec.md").write_text(
        "# foo\nnot a valid spec")
    tier = tmp_path / "tier.txt"
    tier.write_text("owner/repo  # opted in\n")
    r = run("--root", str(root), "--tier-file", str(tier),
            "--repo-name", "owner/repo", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    cls = data["classification"]
    assert cls["state"] == "invalid"
    assert cls["red"] is True


def test_unparseable_tier_file_is_gate_fault(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    tier = tmp_path / "tier.txt"
    tier.write_bytes(b"\xff\xfe\x00\x00not utf8")
    r = run("--root", str(root), "--tier-file", str(tier),
            "--repo-name", "owner/repo", "--json")
    assert r.returncode == 2, (r.returncode, r.stderr)
    assert "gate fault" in r.stderr or "unreadable" in r.stderr


def test_unscannable_never_reads_as_spaced(tmp_path):
    r = run("--root", str(tmp_path / "does-not-exist"),
            "--repo-name", "owner/repo", "--json")
    assert r.returncode == 2


def test_spaced_repo(tmp_path):
    root = make_repo(tmp_path)
    tier = tmp_path / "tier.txt"
    tier.write_text("")
    r = run("--root", str(root), "--tier-file", str(tier),
            "--repo-name", "owner/repo", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    cls = data["classification"]
    # a tiered-or-not repo with openspec material must not crash; any honest
    # state is acceptable (spaced/gaps/invalid/unscannable all mean it ran)
    assert cls["state"] in ("spaced", "gaps", "invalid", "unscannable")
    assert cls["red"] is not True  # not tiered -> never red


def test_missing_validator_is_gate_fault_not_red(tmp_path):
    """SGA-11: a runner without the openspec binary must not red tiered repos.

    Point PATH at an empty dir so the binary genuinely cannot be found, and
    set SPEC_AUDIT_OPENSPEC_BIN to a non-existent file. The classifier must
    fail closed as a gate fault (exit 2) rather than classifying every repo
    invalid/red.
    """
    empty_bin = tmp_path / "emptybin"
    empty_bin.mkdir()
    root = make_repo(tmp_path)
    tier = tmp_path / "tier.txt"
    tier.write_text("owner/repo  # opted in\n")
    env = dict(os.environ)
    env["PATH"] = str(empty_bin)
    env["SPEC_AUDIT_OPENSPEC_BIN"] = str(tmp_path / "no-such-bin")
    r = run("--root", str(root), "--tier-file", str(tier),
            "--repo-name", "owner/repo", "--json", env=env)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    cls = data["classification"]
    # A fleet walk names it `unscannable` with the reason — never spaced, never red.
    assert cls["state"] == "unscannable"
    assert cls["red"] is not True
    assert "not found" in cls["reason"]


def test_provenance_unreachable_upstream_is_unknown_not_in_sync(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    lock = root / "spec-templates.lock.json"
    lock.write_text(json.dumps({
        "templates": {
            "t1": {
                "source": "http://127.0.0.1:1/does-not-exist",
                "pinned_sha256": "a" * 64,
                "upstream_version": "1.0",
                "vendored_path": None,
            }
        }
    }))
    r = run("--lock-check-only", "--lock-file", str(lock), "--json")
    assert r.returncode == 0, r.stderr
    prov = json.loads(r.stdout)
    assert prov.get("fault") is True
    assert "t1" in (prov.get("unknown") or [])
    # and the tree itself is not blamed for the lock's unreachable upstream
    r2 = run("--root", str(root), "--lock-file", str(lock),
             "--repo-name", "owner/repo", "--json")
    assert json.loads(r2.stdout)["provenance"].get("fault") is False


def test_provenance_drift_names_both_hashes_truncated(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    vendored = root / "vendored.md"
    vendored.write_text("hello")
    local_sha = hashlib.sha256(b"hello").hexdigest()
    lock = root / "spec-templates.lock.json"
    lock.write_text(json.dumps({
        "templates": {
            "t1": {
                "source": "http://127.0.0.1:1/does-not-exist",
                "pinned_sha256": "b" * 64,
                "upstream_version": "1.0",
                "vendored_path": "vendored.md",
            }
        }
    }))
    r = run("--root", str(root), "--lock-file", str(lock),
            "--repo-name", "owner/repo", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    prov = data["provenance"]
    drift = prov.get("drift") or []
    assert any(d.get("kind") == "local" for d in drift), prov
    local_entry = [d for d in drift if d.get("kind") == "local"][0]
    assert local_entry["pinned"][:12] == "b" * 12
    assert local_entry["actual"][:12] == local_sha[:12]


def test_tier_matching_is_form_agnostic(tmp_path):
    """A tiered repo must read tiered whether its name arrives owner/repo,
    bare, or as a URL — an opted-in repo that reads unenforced because the
    walk passed a bare local path is a silent tier hole (SGA-11)."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "openspec" / "specs" / "foo").mkdir(parents=True)
    (root / "openspec" / "specs" / "foo" / "spec.md").write_text(
        "# foo\nnot a valid spec")
    tier = tmp_path / "tier.txt"
    tier.write_text("TheArchitectit/AIGGP-Agentic-Framework  # host\n")
    for name in ("AIGGP-Agentic-Framework",
                 "TheArchitectit/AIGGP-Agentic-Framework",
                 "https://github.com/TheArchitectit/AIGGP-Agentic-Framework"):
        r = run("--root", str(root), "--tier-file", str(tier),
                "--repo-name", name, "--json")
        data = json.loads(r.stdout)
        cls = data["classification"]
        assert cls["state"] == "invalid", (name, cls)
        assert cls["tiered"] is True, (name, cls)


def test_tier_entry_without_a_reason_is_gate_fault(tmp_path):
    """A tier entry with no reason is a quiet hole (SGA-11 scenario 4).

    The tier file's own header calls a reason-less entry a hole; the parser
    must refuse the file rather than enforce that hole as if it were a
    reviewed adoption decision. Exit 2, never "the tier is empty".
    """
    root = make_repo(tmp_path, openspec=False)
    tier = tmp_path / "tier.txt"
    tier.write_text("owner/repo\n")
    r = run("--root", str(root), "--tier-file", str(tier), "--json")
    assert r.returncode == 2, r.stdout
    assert "without a reason" in r.stderr


def test_tier_entry_with_a_reason_parses(tmp_path):
    root = make_repo(tmp_path, openspec=False)
    tier = tmp_path / "tier.txt"
    tier.write_text("owner/repo  # opted in, 2026-10-23\n")
    r = run("--root", str(root), "--tier-file", str(tier), "--json")
    assert r.returncode == 0, r.stderr
    cls = json.loads(r.stdout)["classification"]
    assert cls["tiered"] is True


def test_not_vendored_entry_is_not_an_unlocked_finding(tmp_path):
    """vendored_path: null is a documented 'we have no copy yet', not drift.

    Flagging it as unlocked made every sweep red forever on a decision the
    lock itself records.
    """
    root = make_repo(tmp_path, openspec=False)
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({"templates": {"openspec-spec": {
        "source": None, "pinned_sha256": "0" * 64, "vendored_path": None,
    }}}))
    r = run("--root", str(root), "--lock-file", str(lock), "--json")
    assert r.returncode == 0, r.stderr
    prov = json.loads(r.stdout)["provenance"]
    assert prov["unlocked"] == []
    assert prov["drift"] == []
    assert prov["fault"] is False
    # nothing to check in-tree, so no per-tree entry at all
    assert prov["templates"] == {}
    # and the lock level calls the entry what it is
    lock_prov = json.loads(
        run("--lock-check-only", "--lock-file", str(lock), "--json").stdout)
    assert lock_prov["templates"]["openspec-spec"]["status"] == "not-vendored"
    assert lock_prov["drift"] == []


def test_pin_source_that_no_longer_matches_the_pin_is_a_fault(tmp_path):
    """The pin is checked against the URL it was verified at (SGA-22).

    A pinned_sha256 that does not match its own pin_source means the lock is
    lying about its own pin: gate fault, never 'in sync'.
    """
    root = make_repo(tmp_path, openspec=False)
    content = tmp_path / "upstream.md"
    content.write_text("# upstream copy\n")
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({"templates": {"openspec-spec": {
        "source": None,
        "pin_source": content.as_uri(),
        "pinned_sha256": "1" * 64,
        "vendored_path": None,
    }}}))
    r = run("--lock-check-only", "--lock-file", str(lock), "--json")
    assert r.returncode == 0, r.stderr
    prov = json.loads(r.stdout)
    assert prov["fault"] is True
    assert prov["templates"]["openspec-spec"]["pin_source_hash"] != "1" * 64


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([str(Path(__file__))]))
