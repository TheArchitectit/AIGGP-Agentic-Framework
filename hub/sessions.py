#!/usr/bin/env python3
# spec: session-01, session-04, session-05
"""hub/sessions.py - ingest .guardrails/sessions.jsonl and join registry hits.

The brain (`scripts/game_session_start.py`) appends one canonical JSON line per
accepted `work` or `play` session to `<root>/.guardrails/sessions.jsonl`. This
module is the hub's pure reader over that log:

  - Every row is re-checked against the `aiggp.session/v1` contract so a
    malformed or hand-edited line is quarantined in `rejected`, never silently
    counted or allowed to crash the view.
  - A missing or unreadable `sessions.jsonl` returns `state: "unknown"` (never
    `0` sessions with a green status).
  - `join_with_registry(sessions, registry_entries)` links play/work sessions to
    failure-registry rows via `capture.stream_id == entry.stream_id` (primary
    join key) or matching non-empty `seed` (fallback when `stream_id` was not
    recorded), as specified in `docs/REDEYE-SESSION-CONTRACT.md`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SCHEMA_ID = "aiggp.session/v1"
LOG_REL = Path(".guardrails") / "sessions.jsonl"
REGISTRY_REL = Path(".guardrails") / "failure-registry.jsonl"
UTC_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
OPENED_BY_RE = re.compile(r"^(runtime|agent):\S+$")


def _non_empty_str(val) -> bool:
    return isinstance(val, str) and bool(val.strip())


def validate_session_row(row) -> tuple[bool, str]:
    """Validate one parsed JSON value against the `aiggp.session/v1` shape."""
    if not isinstance(row, dict):
        return False, "row is not a JSON object"
    if row.get("schema") != SCHEMA_ID:
        return False, f"unexpected schema {row.get('schema')!r}"
    if row.get("kind") not in ("play", "work"):
        return False, f"invalid kind {row.get('kind')!r}"
    if not _non_empty_str(row.get("game")):
        return False, "missing or empty game"
    opened_at = row.get("opened_at")
    if not isinstance(opened_at, str) or not UTC_TS_RE.match(opened_at):
        return False, f"invalid opened_at {opened_at!r}"
    opened_by = row.get("opened_by")
    if not isinstance(opened_by, str) or not OPENED_BY_RE.match(opened_by):
        return False, f"invalid opened_by {opened_by!r}"
    if "capture" in row:
        cap = row["capture"]
        if not isinstance(cap, dict) or not _non_empty_str(cap.get("stream_id")):
            return False, "capture block lacks non-empty stream_id"
    if "scope" in row:
        scope = row["scope"]
        if (not isinstance(scope, list) or not scope
                or not all(_non_empty_str(s) for s in scope)):
            return False, "scope must be a non-empty list of non-blank globs"
    return True, ""


def load_sessions(log_path: Path) -> dict:
    """Read `sessions.jsonl` into a structured, defensively-typed summary.

    Returns:
      {
        "state": "known" | "unknown",
        "reason": str,
        "source": str,
        "total": int | None,
        "by_kind": {"play": int, "work": int} | None,
        "by_game": dict[str, int],
        "sessions": list[dict],
        "rejected": list[{"line": int, "reason": str}],
      }
    """
    path = Path(log_path)
    base = {
        "state": "unknown",
        "reason": "",
        "source": str(path),
        "total": None,
        "by_kind": None,
        "by_game": {},
        "sessions": [],
        "rejected": [],
    }
    if not path.exists():
        base["reason"] = f"no sessions log at {path}"
        return base
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        base["reason"] = f"sessions log unreadable: {exc}"
        return base

    sessions: list[dict] = []
    rejected: list[dict] = []
    by_kind = {"play": 0, "work": 0}
    by_game: dict[str, int] = {}

    for lineno, raw in enumerate(raw_lines, 1):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            doc = json.loads(stripped)
        except json.JSONDecodeError as exc:
            rejected.append({"line": lineno, "reason": f"invalid JSON: {exc}"})
            continue
        ok, err = validate_session_row(doc)
        if not ok:
            rejected.append({"line": lineno, "reason": err})
            continue
        sessions.append(doc)
        by_kind[doc["kind"]] += 1
        by_game[doc["game"]] = by_game.get(doc["game"], 0) + 1

    return {
        "state": "known",
        "reason": "",
        "source": str(path),
        "total": len(sessions),
        "by_kind": by_kind,
        "by_game": by_game,
        "sessions": sessions,
        "rejected": rejected,
    }


def load_registry_entries(registry_path: Path) -> list[dict]:
    """Load valid dict rows from a `.guardrails/failure-registry.jsonl` file."""
    path = Path(registry_path)
    if not path.exists():
        return []
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict] = []
    for raw in raw_lines:
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            doc = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(doc, dict) and _non_empty_str(doc.get("failure_id")):
            out.append(doc)
    return out


def join_with_registry(sessions: list[dict],
                       registry_entries: list[dict]) -> list[dict]:
    """Join accepted session rows with failure-registry entries.

    Join precedence per `docs/REDEYE-SESSION-CONTRACT.md`:
      1. `stream_id`: when both the session (`capture.stream_id`) and the
         registry entry (`stream_id`) carry the same non-empty string.
      2. `seed`: when the registry entry carries no `stream_id`, or as a
         secondary match when `session.seed == entry.seed` (non-empty).

    Returns one record per session that matched at least one registry entry:
      {
        "session": dict,
        "matched_on": ["stream_id" | "seed", ...],
        "failures": list[dict],
      }
    """
    joined: list[dict] = []
    for sess in sessions:
        if not isinstance(sess, dict):
            continue
        cap = sess.get("capture") if isinstance(sess.get("capture"), dict) else {}
        sess_stream = cap.get("stream_id") if _non_empty_str(cap.get("stream_id")) else None
        sess_seed = sess.get("seed") if _non_empty_str(sess.get("seed")) else None
        if not sess_stream and not sess_seed:
            continue

        matched_failures: list[dict] = []
        reasons: list[str] = []
        for entry in registry_entries:
            if not isinstance(entry, dict):
                continue
            ent_stream = entry.get("stream_id") if _non_empty_str(entry.get("stream_id")) else None
            ent_seed = entry.get("seed") if _non_empty_str(entry.get("seed")) else None
            if sess_stream and ent_stream and sess_stream == ent_stream:
                matched_failures.append(entry)
                if "stream_id" not in reasons:
                    reasons.append("stream_id")
            elif sess_seed and ent_seed and sess_seed == ent_seed and not ent_stream:
                matched_failures.append(entry)
                if "seed" not in reasons:
                    reasons.append("seed")

        if matched_failures:
            joined.append({
                "session": sess,
                "matched_on": reasons,
                "failures": matched_failures,
            })
    return joined


def project_sessions_view(root: Path) -> dict:
    """Build the complete hub session view for a project root."""
    root = Path(root)
    summary = load_sessions(root / LOG_REL)
    entries = load_registry_entries(root / REGISTRY_REL)
    summary["joined_failures"] = join_with_registry(summary["sessions"], entries)
    return summary
