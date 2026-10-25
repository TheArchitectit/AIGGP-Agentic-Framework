#!/usr/bin/env python3
"""Fixture tests for game_session_start.py - the gameSessionStart brain.

Each test pins a rule the design's spec names (session-01..session-06), not an
implementation detail: the manifest shape and its two conditionals, the one
hard rule across determinism x seed, the kind-filtered advisory block and its
honest-empty lines, the append-only log, the gap line reading the scanner's
report instead of rescanning, and the exit-code contract (2 refuses a known
session, 1 cannot say - the inverse of the secret-scan family).

    python3 -m pytest tests/test_game_session_start.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "game_session_start.py"
sys.path.insert(0, str(REPO / "scripts"))

import game_session_start as brain  # noqa: E402


# --- fixtures ---------------------------------------------------------------
def work(**overrides) -> dict:
    manifest = {
        "schema": "aiggp.session/v1",
        "kind": "work",
        "game": "mergekingdom",
        "phase": "alpha",
        "opened_at": "2026-10-25T09:00:00Z",
        "opened_by": "agent:claude-code",
        "scope": ["src/autoload/**", "data/**"],
        "agent": {"carrier": "claude-code", "session_id": "abc"},
    }
    manifest.update(overrides)
    return manifest


def play(**overrides) -> dict:
    manifest = {
        "schema": "aiggp.session/v1",
        "kind": "play",
        "game": "mergekingdom",
        "phase": "alpha",
        "opened_at": "2026-10-25T09:00:00Z",
        "opened_by": "runtime:godot-4.6",
        "seed": "1337",
        "scene": "res://scenes/main.tscn",
        "build": "0.1.0-beta",
    }
    manifest.update(overrides)
    return manifest


def write_game_manifest(root: Path, **determinism) -> None:
    (root / "game-manifest.json").write_text(
        json.dumps({"engine": "Godot", "determinism": determinism}),
        encoding="utf-8")


def write_gap_report(root: Path, report: dict | None = None, *,
                     raw: str | None = None) -> Path:
    path = root / ".guardrails" / "spec-gap-report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        path.write_text(raw, encoding="utf-8")
        return path
    if report is None:
        report = {
            "root": str(root),
            "inventory": {"capabilities": 3, "unspaced": [
                {"capability": "merge-engine", "evidence": "src/merge.gd:1-40"}],
                "partially_tracked": []},
            "coverage": {"requirement_ids": 9, "uncovered_ids": [
                {"id": "mk-01", "capability": "merge-engine",
                 "evidence": "openspec/specs/merge-engine/spec.md"}]},
            "claimed_but_absent": [{"kind": "symbol", "claim": "MAX_HEROES"}],
            "summary": {"unspaced": 1, "partially_tracked": 2,
                        "uncovered_ids": 4, "claimed_but_absent": 1},
        }
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def run(root: Path, manifest: dict | None = None, *,
        stdin_text: str | None = None, extra: tuple[str, ...] = ()):
    args = [sys.executable, str(SCRIPT), "--root", str(root)]
    if manifest is not None:
        path = root / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        args += ["--manifest", str(path)]
    if stdin_text is not None:
        args.append("--stdin")
    args += list(extra)
    return subprocess.run(args, input=stdin_text or "", capture_output=True,
                          text=True, encoding="utf-8")


def log_rows(root: Path) -> list[dict]:
    path = root / ".guardrails" / "sessions.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# --- session-01: the manifest contract --------------------------------------
def test_a_valid_work_manifest_is_accepted_and_logged_once(tmp_path):
    result = run(tmp_path, work())
    assert result.returncode == 0, result.stderr
    rows = log_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0]["schema"] == "aiggp.session/v1"
    assert rows[0]["kind"] == "work"
    assert rows[0]["agent"]["carrier"] == "claude-code"


def test_an_unknown_field_is_refused_and_nothing_is_logged(tmp_path):
    result = run(tmp_path, work(ticket="T-1"))
    assert result.returncode == 2
    assert "unknown field 'ticket'" in result.stderr
    assert log_rows(tmp_path) == []


def test_a_missing_required_field_is_refused(tmp_path):
    manifest = work()
    del manifest["kind"]
    result = run(tmp_path, manifest)
    assert result.returncode == 2
    assert "missing required field 'kind'" in result.stderr
    assert log_rows(tmp_path) == []


def test_an_unknown_kind_is_refused(tmp_path):
    result = run(tmp_path, work(kind="session"))
    assert result.returncode == 2
    assert "not in enum" in result.stderr


def test_a_non_utc_opened_at_is_refused(tmp_path):
    result = run(tmp_path, work(opened_at="2026-10-25T09:00:00+02:00"))
    assert result.returncode == 2
    assert "manifest.opened_at" in result.stderr


def test_a_manifest_that_does_not_parse_is_refused_not_crashed(tmp_path):
    result = run(tmp_path, stdin_text="{not json")
    assert result.returncode == 2
    assert "does not parse as JSON" in result.stderr


def test_a_non_object_manifest_is_refused(tmp_path):
    result = run(tmp_path, stdin_text="[]")
    assert result.returncode == 2
    assert "not a JSON object" in result.stderr


def test_a_capture_block_without_a_stream_id_is_refused(tmp_path):
    result = run(tmp_path, work(capture={"review": True}))
    assert result.returncode == 2
    assert "stream_id" in result.stderr
    assert log_rows(tmp_path) == []


def test_the_capture_rule_is_conditional_not_unconditional(tmp_path):
    """Declaring no capture must validate: the rule fires only when the block
    is present (a manifest without capture is not an invalid one)."""
    result = run(tmp_path, work())
    assert result.returncode == 0
    assert "capture: none" in result.stdout


# --- session-02: the one hard rule ------------------------------------------
def test_play_under_determinism_with_a_seed_is_accepted(tmp_path):
    write_game_manifest(tmp_path, enabled=True)
    result = run(tmp_path, play())
    assert result.returncode == 0, result.stderr
    assert "determinism: enabled" in result.stdout


def test_play_under_determinism_without_a_seed_is_refused(tmp_path):
    write_game_manifest(tmp_path, enabled=True)
    manifest = play()
    del manifest["seed"]
    result = run(tmp_path, manifest)
    assert result.returncode == 2
    assert "no non-empty seed" in result.stderr
    assert log_rows(tmp_path) == []


def test_play_under_determinism_with_a_blank_seed_is_refused(tmp_path):
    write_game_manifest(tmp_path, enabled=True)
    result = run(tmp_path, play(seed="   "))
    assert result.returncode == 2
    assert "no non-empty seed" in result.stderr


def test_play_under_determinism_off_needs_no_seed(tmp_path):
    write_game_manifest(tmp_path, enabled=False)
    manifest = play()
    del manifest["seed"]
    result = run(tmp_path, manifest)
    assert result.returncode == 0, result.stderr
    assert "determinism: off" in result.stdout


def test_an_undeclared_determinism_key_means_off(tmp_path):
    """Absent key = off: a project that never declared a policy cannot be
    broken retroactively, so the rule is opt-in."""
    (tmp_path / "game-manifest.json").write_text('{"engine": "Godot"}')
    manifest = play()
    del manifest["seed"]
    result = run(tmp_path, manifest)
    assert result.returncode == 0, result.stderr
    assert "determinism: not-declared" in result.stdout


def test_play_in_a_root_without_a_game_manifest_is_refused(tmp_path):
    result = run(tmp_path, play())
    assert result.returncode == 2
    assert "game-manifest.json is absent" in result.stderr
    assert log_rows(tmp_path) == []


def test_work_without_a_game_manifest_proceeds_with_an_unknown_banner(tmp_path):
    result = run(tmp_path, work())
    assert result.returncode == 0, result.stderr
    assert "determinism: unknown" in result.stdout


def test_a_non_boolean_determinism_flag_cannot_be_read(tmp_path):
    (tmp_path / "game-manifest.json").write_text(
        '{"determinism": {"enabled": "yes"}}')
    result = run(tmp_path, play())
    assert result.returncode == 1
    assert "cannot say" in result.stderr
    assert "not a boolean" in result.stderr


def test_no_manifest_supplied_cannot_say(tmp_path):
    result = run(tmp_path)
    assert result.returncode == 1
    assert "no manifest supplied" in result.stderr


# --- session-03: the advisory block -----------------------------------------
def test_the_work_advisory_carries_every_block(tmp_path):
    (tmp_path / ".guardrails").mkdir()
    (tmp_path / ".guardrails" / "pre-work-check.md").write_text("# check\n")
    result = run(tmp_path, work())
    out = result.stdout
    assert "work session in mergekingdom (agent:claude-code)" in out
    assert "phase: alpha" in out
    assert "phase gates: unknown" in out
    assert "determinism:" in out
    assert "registry hits (" in out
    assert "pre-work check: .guardrails/pre-work-check.md" in out
    assert "worst-tracked gaps:" in out
    assert "capture: none" in out


def test_an_absent_phase_lists_no_gates(tmp_path):
    manifest = work()
    del manifest["phase"]
    out = run(tmp_path, manifest).stdout
    assert "phase: unknown - no phase claimed, no gates listed" in out
    assert "phase gates:" not in out


def test_a_declared_capture_names_the_inspection_surface(tmp_path):
    out = run(tmp_path, work(capture={"stream_id": "mk-alpha-1337",
                                      "review": True})).stdout
    assert "capture: stream mk-alpha-1337" in out
    assert "get_frame" in out and "semantic_diff" in out
    assert "capture: none" not in out


def test_the_play_advisory_has_no_gap_line_and_a_screen_pointer(tmp_path):
    write_game_manifest(tmp_path, enabled=True)
    write_gap_report(tmp_path)
    out = run(tmp_path, play()).stdout
    assert "worst-tracked gaps:" not in out
    assert "screen inventory: not evaluated" in out
    assert "pre-work check:" not in out


def test_an_unreadable_registry_reads_as_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(brain.gate_overlay, "resolve_registry",
                        lambda root: ([], {}))
    hits, detail = brain.registry_hits(tmp_path, ["src/**"])
    assert hits is None
    assert "no failure-registry entries readable" in detail
    lines = brain.advisory(work(), tmp_path, ("unknown", "no manifest"), {
        "state": "unknown", "count": None, "worst": None, "reason": "none"})
    assert any("registry hits: unknown" in line for line in lines)


def test_registry_advice_is_scope_filtered_and_skips_resolved(tmp_path,
                                                              monkeypatch):
    entries = [
        {"failure_id": "FAIL-b", "status": "active", "severity": "high",
         "error_message": "in scope", "affected_files": ["src/autoload/game.gd"]},
        {"failure_id": "FAIL-a", "status": "active", "severity": "high",
         "error_message": "elsewhere", "affected_files": ["docs/readme.md"]},
        {"failure_id": "FAIL-c", "status": "resolved", "severity": "high",
         "error_message": "fixed", "affected_files": ["src/autoload/game.gd"]},
    ]
    monkeypatch.setattr(brain.gate_overlay, "resolve_registry",
                        lambda root: (entries, {}))
    hits, _detail = brain.registry_hits(tmp_path, ["src/autoload/**"])
    assert [entry["failure_id"] for entry in hits] == ["FAIL-b"]


def test_guardrailsignore_filters_advice_only(tmp_path, monkeypatch):
    entries = [{"failure_id": "FAIL-a", "status": "active", "severity": "high",
                "error_message": "in scope",
                "affected_files": ["src/autoload/game.gd"]}]
    monkeypatch.setattr(brain.gate_overlay, "resolve_registry",
                        lambda root: (entries, {}))
    (tmp_path / ".guardrailsignore").write_text("src/autoload/**\n")
    hits, _detail = brain.registry_hits(tmp_path, ["src/autoload/**"])
    assert hits == []


# --- session-05: the gap line reads the report ------------------------------
def test_the_gap_line_counts_what_the_scanner_gates_on(tmp_path):
    write_gap_report(tmp_path)
    out = run(tmp_path, work()).stdout
    # unspaced 1 + partially_tracked 2 + uncovered_ids 4; claimed-but-absent
    # (1) never contributes - the scanner's own rule.
    assert "worst-tracked gaps: 7" in out
    assert "worst: merge-engine [src/merge.gd:1-40]" in out


def test_the_gap_number_is_read_not_recomputed(tmp_path):
    """The fixture root has no sources at all; a rescan would report 0/exit 2.
    Rendering the report's own 7 proves the brain consumed the report."""
    write_gap_report(tmp_path)
    assert not any(tmp_path.glob("src"))
    assert "worst-tracked gaps: 7" in run(tmp_path, work()).stdout


def test_a_report_for_another_root_is_unknown(tmp_path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    write_gap_report(tmp_path, {"root": str(other),
                                "summary": {"unspaced": 1,
                                            "partially_tracked": 0,
                                            "uncovered_ids": 0}})
    out = run(tmp_path, work()).stdout
    assert "worst-tracked gaps: unknown" in out
    assert "not this root" in out


def test_a_malformed_report_is_unknown(tmp_path):
    write_gap_report(tmp_path, raw="{oops")
    out = run(tmp_path, work()).stdout
    assert "worst-tracked gaps: unknown" in out
    assert "unreadable" in out


def test_a_report_that_is_not_the_scanners_shape_is_unknown(tmp_path):
    write_gap_report(tmp_path, {"root": str(tmp_path), "summary": {"gaps": 3}})
    out = run(tmp_path, work()).stdout
    assert "worst-tracked gaps: unknown" in out
    assert "not the scanner's --json shape" in out


def test_an_absent_report_is_unknown_never_zero(tmp_path):
    out = run(tmp_path, work()).stdout
    assert "worst-tracked gaps: unknown" in out
    assert "worst-tracked gaps: 0" not in out


def test_an_explicit_gap_report_path_is_honoured(tmp_path):
    write_game_manifest(tmp_path, enabled=True)
    elsewhere = tmp_path / "reports" / "gap.json"
    elsewhere.parent.mkdir()
    elsewhere.write_text(json.dumps({
        "root": str(tmp_path),
        "summary": {"unspaced": 0, "partially_tracked": 0,
                    "uncovered_ids": 2}}))
    out = run(tmp_path, work(), extra=("--gap-report", str(elsewhere))).stdout
    assert "worst-tracked gaps: 2" in out


# --- session-04: the append-only log ----------------------------------------
def test_a_reopened_session_appends_a_second_row(tmp_path):
    run(tmp_path, work())
    run(tmp_path, work())
    rows = log_rows(tmp_path)
    assert len(rows) == 2
    assert rows[0] == rows[1]


def test_the_log_directory_is_created(tmp_path):
    assert not (tmp_path / ".guardrails").exists()
    run(tmp_path, work())
    assert (tmp_path / ".guardrails" / "sessions.jsonl").exists()


def test_a_play_row_carries_seed_and_stream_id(tmp_path):
    write_game_manifest(tmp_path, enabled=True)
    result = run(tmp_path, play(capture={"stream_id": "mk-alpha-1337",
                                         "review": True}))
    assert result.returncode == 0, result.stderr
    row = log_rows(tmp_path)[0]
    assert row["seed"] == "1337"
    assert row["capture"]["stream_id"] == "mk-alpha-1337"


# --- session-06: the exit-code contract -------------------------------------
def test_a_refusal_is_two_and_a_malfunction_is_one(tmp_path):
    assert run(tmp_path, work(kind="session")).returncode == 2
    assert run(tmp_path).returncode == 1


def test_the_machine_result_carries_the_advisory_and_the_gap(tmp_path):
    write_gap_report(tmp_path)
    result = run(tmp_path, work(), extra=("--json",))
    assert result.returncode == 0, result.stderr
    doc = json.loads(result.stdout)
    assert doc["verdict"] == "accepted"
    assert doc["gap"]["state"] == "known"
    assert doc["gap"]["count"] == 7
    assert doc["log"] == ".guardrails/sessions.jsonl"
    assert any("worst-tracked gaps: 7" in line for line in doc["advisory"])
