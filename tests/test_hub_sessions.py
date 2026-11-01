#!/usr/bin/env python3
"""Tests for hub/sessions.py - sessions.jsonl ingestion and registry join."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
BRAIN = REPO / "scripts" / "game_session_start.py"
LOG_FAILURE = REPO / "scripts" / "log_failure.py"
sys.path.insert(0, str(REPO))

from hub import sessions as hs  # noqa: E402


def _work_row(**overrides) -> dict:
    doc = {
        "schema": "aiggp.session/v1",
        "kind": "work",
        "game": "mergekingdom",
        "phase": "alpha",
        "opened_at": "2026-11-01T10:00:00Z",
        "opened_by": "agent:claude-code",
        "agent": {"carrier": "claude-code", "session_id": "s-1"},
    }
    doc.update(overrides)
    return doc


def _play_row(**overrides) -> dict:
    doc = {
        "schema": "aiggp.session/v1",
        "kind": "play",
        "game": "mergekingdom",
        "phase": "alpha",
        "opened_at": "2026-11-01T10:05:00Z",
        "opened_by": "runtime:godot-4.7",
        "seed": "1337",
        "scene": "res://src/main/Main.tscn",
        "capture": {"stream_id": "mergekingdom-alpha-1337", "review": True},
    }
    doc.update(overrides)
    return doc


def test_absent_sessions_log_is_unknown_never_zero(tmp_path):
    res = hs.load_sessions(tmp_path / ".guardrails" / "sessions.jsonl")
    assert res["state"] == "unknown"
    assert res["total"] is None
    assert res["by_kind"] is None
    assert "no sessions log" in res["reason"]


def test_ingests_valid_work_and_play_rows_and_quarantines_malformed(tmp_path):
    log = tmp_path / ".guardrails" / "sessions.jsonl"
    log.parent.mkdir(parents=True)
    lines = [
        json.dumps(_work_row()),
        json.dumps(_play_row()),
        "{not-json",
        json.dumps({"schema": "wrong/v1", "kind": "work"}),
        json.dumps(_play_row(opened_at="2026-11-01T10:05:00+02:00")),
    ]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    res = hs.load_sessions(log)
    assert res["state"] == "known"
    assert res["total"] == 2
    assert res["by_kind"] == {"play": 1, "work": 1}
    assert res["by_game"] == {"mergekingdom": 2}
    assert len(res["rejected"]) == 3
    assert [r["line"] for r in res["rejected"]] == [3, 4, 5]


def test_join_with_registry_matches_stream_id_and_seed_fallback():
    play1 = _play_row(seed="1337", capture={"stream_id": "mk-alpha-1337", "review": True})
    play2 = _play_row(seed="9001")
    del play2["capture"]
    reg = [
        {
            "failure_id": "FAIL-stream",
            "stream_id": "mk-alpha-1337",
            "seed": "1337",
            "error_message": "frame 42 mismatch",
        },
        {
            "failure_id": "FAIL-seed-only",
            "seed": "9001",
            "error_message": "seeded crash",
        },
        {
            "failure_id": "FAIL-other",
            "stream_id": "mk-alpha-9999",
            "seed": "1337",
            "error_message": "different stream with same seed must not cross-join",
        },
    ]
    joined = hs.join_with_registry([play1, play2], reg)
    assert len(joined) == 2
    assert joined[0]["matched_on"] == ["stream_id"]
    assert [f["failure_id"] for f in joined[0]["failures"]] == ["FAIL-stream"]
    assert joined[1]["matched_on"] == ["seed"]
    assert [f["failure_id"] for f in joined[1]["failures"]] == ["FAIL-seed-only"]


def test_end_to_end_brain_to_log_failure_to_hub_sessions_view(tmp_path):
    (tmp_path / "game-manifest.json").write_text(
        json.dumps({"engine": "Godot", "determinism": {"enabled": True}}),
        encoding="utf-8",
    )
    r1 = subprocess.run(
        [sys.executable, str(BRAIN), "--stdin", "--root", str(tmp_path)],
        input=json.dumps(_play_row()),
        capture_output=True,
        text=True,
    )
    assert r1.returncode == 0, r1.stderr
    reg_path = tmp_path / ".guardrails" / "failure-registry.jsonl"
    r2 = subprocess.run(
        [
            sys.executable,
            str(LOG_FAILURE),
            "--error-message", "DETERMINISM gate failed on frame 12",
            "--affected-files", "src/autoload/game_manager.gd",
            "--seed", "1337",
            "--stream-id", "mergekingdom-alpha-1337",
            "--status", "active",
            "--registry", str(reg_path),
        ],
        capture_output=True,
        text=True,
    )
    assert r2.returncode == 0, r2.stderr
    view = hs.project_sessions_view(tmp_path)
    assert view["state"] == "known"
    assert view["total"] == 1
    assert len(view["joined_failures"]) == 1
    assert view["joined_failures"][0]["matched_on"] == ["stream_id"]
    assert "DETERMINISM gate failed" in view["joined_failures"][0]["failures"][0]["error_message"]
