#!/usr/bin/env python3
"""Unit tests for scripts/gate_common.py — the shared gate primitives.

Locks one behaviour per historical divergence:
  * root detection is the layout contract (never a marker walk-up)
  * SKIP_DIRS comes from .guardrails/scope.json (load, never redeclare)
  * JSONL parse errors are reported, missing file is an error not []
  * line_has_allow requires reason text and keys on the id
  * glob_matches covers basename, path, **, and zero-directory /**
  * load_ignore_patterns / is_ignored share one .guardrailsignore contract
  * nothing_scanned is a report + exit code, never a bare green
  * detect_package_manager covers go and godot
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"

sys.path.insert(0, str(SCRIPTS))
import gate_common  # noqa: E402


def test_project_root_layout_submodule(tmp_path):
    dg = tmp_path / ".devgate"
    dg.mkdir()
    assert gate_common.project_root_for(dg) == tmp_path


def test_project_root_layout_standalone(tmp_path):
    assert gate_common.project_root_for(tmp_path) == tmp_path


def test_project_root_never_walks_parents(tmp_path, monkeypatch):
    """A marker above the checkout must not steal the root (the audit escape)."""
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    assert gate_common.project_root_for(repo) == repo


def test_project_root_env_override(tmp_path, monkeypatch):
    point = tmp_path / "fixture"
    point.mkdir()
    monkeypatch.setenv("DEVGATE_PROJECT_ROOT", str(point))
    assert gate_common.project_root() == point.resolve()


def test_load_skip_dirs_reads_scope_contract(tmp_path):
    dg = tmp_path / ".devgate"
    (dg / ".guardrails").mkdir(parents=True)
    (dg / ".guardrails" / "scope.json").write_text(
        json.dumps({"skip_dirs": ["node_modules", ".git"]}), encoding="utf-8")
    assert gate_common.load_skip_dirs(dg) == frozenset({"node_modules", ".git"})


def test_load_skip_dirs_project_overlay_wins(tmp_path):
    proj = tmp_path
    dg = proj / ".devgate"
    (dg / ".guardrails").mkdir(parents=True)
    (dg / ".guardrails" / "scope.json").write_text(
        json.dumps({"skip_dirs": ["node_modules"]}), encoding="utf-8")
    (proj / ".guardrails").mkdir()
    (proj / ".guardrails" / "scope.json").write_text(
        json.dumps({"skip_dirs": ["node_modules", "extras"]}), encoding="utf-8")
    assert gate_common.load_skip_dirs(dg) == frozenset({"node_modules", "extras"})


def test_load_skip_dirs_missing_contract_raises(tmp_path):
    try:
        gate_common.load_skip_dirs(tmp_path)
    except FileNotFoundError as exc:
        assert "scope.json" in str(exc)
    else:
        raise AssertionError("missing scope contract must raise, not return []")


def test_read_jsonl_registry_reports_parse_errors(tmp_path):
    p = tmp_path / "reg.jsonl"
    p.write_text('{"failure_id":"a"}\n# comment\n\n{not json}\n', encoding="utf-8")
    entries, errors = gate_common.read_jsonl_registry(p)
    assert entries == [{"failure_id": "a"}]
    assert len(errors) == 1
    assert errors[0].startswith("line 4:")


def test_read_jsonl_registry_missing_file_is_error_not_empty(tmp_path):
    entries, errors = gate_common.read_jsonl_registry(tmp_path / "nope.jsonl")
    assert entries == []
    assert errors == [f"registry not found: {tmp_path / 'nope.jsonl'}"]


def test_line_has_allow_requires_reason():
    assert gate_common.line_has_allow("// guardrails-allow RULE-1: tested", "RULE-1")
    assert not gate_common.line_has_allow("// guardrails-allow RULE-1:", "RULE-1")
    assert not gate_common.line_has_allow("// guardrails-allow RULE-1:   ", "RULE-1")


def test_line_has_allow_keys_on_id():
    line = "// guardrails-allow RULE-1: covers this one only"
    assert gate_common.line_has_allow(line, "RULE-1")
    assert not gate_common.line_has_allow(line, "RULE-10")
    assert not gate_common.line_has_allow(line, "RULE-10", "")


def test_glob_matches_basename_and_path():
    assert gate_common.glob_matches("src/foo.py", ["*.py"])
    assert gate_common.glob_matches("src/foo.py", ["src/*.py"])
    assert not gate_common.glob_matches("src/foo.py", ["*.rs"])


def test_glob_matches_globstar_zero_segment():
    assert gate_common.glob_matches("a/b", ["a/**/b"])
    assert gate_common.glob_matches("a/x/b", ["a/**/b"])
    assert gate_common.glob_matches("src/a.rs", ["src/**/*"])
    assert gate_common.glob_matches("src/a/b.rs", ["src/**/*"])


def test_glob_matches_empty_and_none():
    assert not gate_common.glob_matches("x.py", [])
    assert not gate_common.glob_matches("x.py", None)


def test_nothing_scanned_reports_and_exits():
    # capsys is not required — the helper returns the code; the marker text is
    # the shared contract the existing suite greps for.
    assert gate_common.nothing_scanned("unit", "no files under scope") == 0
    assert gate_common.nothing_scanned("unit", "empty", fail_if_empty=True) == 2


def test_detect_package_manager_includes_go_and_godot(tmp_path):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    assert gate_common.detect_package_manager(tmp_path) == "npm"

    go = tmp_path / "go"
    go.mkdir()
    (go / "go.mod").write_text("", encoding="utf-8")
    assert gate_common.detect_package_manager(go) == "go"

    god = tmp_path / "god"
    god.mkdir()
    (god / "project.godot").write_text("", encoding="utf-8")
    assert gate_common.detect_package_manager(god) == "godot"

    empty = tmp_path / "empty"
    empty.mkdir()
    assert gate_common.detect_package_manager(empty) is None


def test_load_ignore_patterns_skips_blanks_and_comments(tmp_path):
    (tmp_path / ".guardrailsignore").write_text(
        "# frozen legacy\n\narchive/\n*.snap\n", encoding="utf-8")
    assert gate_common.load_ignore_patterns(tmp_path) == ["archive/", "*.snap"]


def test_load_ignore_patterns_missing_file_is_empty(tmp_path):
    assert gate_common.load_ignore_patterns(tmp_path) == []


def test_is_ignored_relpath_basename_and_dir_prefix(tmp_path):
    pats = ["archive/", "*.snap"]
    assert gate_common.is_ignored(str(tmp_path / "archive" / "old.py"), tmp_path, pats)
    assert gate_common.is_ignored(str(tmp_path / "x.snap"), tmp_path, pats)
    assert gate_common.is_ignored(str(tmp_path / "src" / "y.snap"), tmp_path, pats)
    assert not gate_common.is_ignored(str(tmp_path / "src" / "keep.py"), tmp_path, pats)
    assert not gate_common.is_ignored(str(tmp_path / "src" / "keep.py"), tmp_path, [])