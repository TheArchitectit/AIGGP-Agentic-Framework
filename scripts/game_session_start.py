#!/usr/bin/env python3
# spec: session-01, session-02, session-03, session-04, session-05, session-06
"""game_session_start.py - gameSessionStart brain: one manifest, two sides.

A work-session (an agent opening a game repo to edit) and a play-session (the
runtime booting a run) are described by the same manifest (`aiggp.session/v1`).
This module is the one place that validates it, applies the one hard rule,
assembles the kind-filtered advisory block and appends an accepted session to
the append-only log. Carriers are thin adapters that call it and speak their
host's idiom; business logic in an adapter is a defect.

Design: docs/superpowers/specs/2026-09-29-game-session-start-design.md
Spec:   openspec/changes/add-game-session-start/specs/game-session-start/spec.md

Exit codes - deliberately NOT the secret-scan family's (session-06):
    0  accepted: valid manifest, advisory printed, session appended to
       .guardrails/sessions.jsonl
    2  refused a known session: schema-invalid manifest, a play-session under
       determinism with no seed, or a play-session in a root with no
       game-manifest.json. Nothing is logged on a refusal.
    1  cannot say: the brain cannot evaluate at all (unreadable schema, no
       manifest supplied, unreadable game-manifest.json). Never a pass.
A runner wiring either family into CI must not guess; the contrast is stated
in the spec, not unified away.

The advisory's gap line (session-05) reads the spec-gap scanner's JSON report
and never runs the scanner - one inventory source (SGA-01). A missing, foreign
or malformed report prints an explicit unknown, never 0.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_common  # noqa: E402
import gate_overlay  # noqa: E402

DEVGATE_ROOT = gate_common.devgate_root()
SCHEMA_PATH = (DEVGATE_ROOT / ".guardrails" / "prevention-rules"
               / "session-manifest.schema.json")
LOG_REL = Path(".guardrails") / "sessions.jsonl"
GAP_REPORT_REL = Path(".guardrails") / "spec-gap-report.json"
PRE_WORK_REL = Path(".guardrails") / "pre-work-check.md"
REGISTRY_ADVICE_LIMIT = 5
ADVICE_TEXT_LIMIT = 100
GAP_SUMMARY_KEYS = ("unspaced", "partially_tracked", "uncovered_ids")
EXIT_OK, EXIT_CANNOT_SAY, EXIT_REFUSED = 0, 1, 2


class BrainError(Exception):
    """The brain cannot say (exit 1) - never a verdict about the session."""


# --- the Draft-07 subset -----------------------------------------------------
# Same subset rules_check.py validates its rules with, plus minLength/minItems:
# enough for the manifest shape, deliberately NOT enough for conditionals (see
# the schema's description and session-01). One implementation lives here for
# the brain; rules_check keeps its own for its own schema.
def _is_type(value, want: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "null": value is None,
    }.get(want, True)


def _resolve_ref(ref: str, root: dict):
    node = root
    for part in ref.lstrip("#/").split("/"):
        if part:
            node = node[part]
    return node


def validate(instance, schema: dict, root: dict, path: str,
             errors: list[str]) -> None:
    if "$ref" in schema:
        validate(instance, _resolve_ref(schema["$ref"], root), root, path, errors)
        return
    want = schema.get("type")
    if want:
        types = want if isinstance(want, list) else [want]
        if not any(_is_type(instance, t) for t in types):
            errors.append(f"{path}: expected type {types}, "
                          f"got {type(instance).__name__}")
            return
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in enum {schema['enum']}")
    if "pattern" in schema and isinstance(instance, str):
        if not re.search(schema["pattern"], instance):
            errors.append(f"{path}: {instance!r} does not match "
                          f"pattern {schema['pattern']!r}")
    if "minLength" in schema and isinstance(instance, str):
        if len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than {schema['minLength']} characters")
    if "minItems" in schema and isinstance(instance, list):
        if len(instance) < schema["minItems"]:
            errors.append(f"{path}: fewer than {schema['minItems']} items")
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required field '{key}'")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    errors.append(f"{path}: unknown field '{key}'")
        for key, sub in props.items():
            if key in instance:
                validate(instance[key], sub, root, f"{path}.{key}", errors)
    if isinstance(instance, list) and "items" in schema:
        for i, item in enumerate(instance):
            validate(item, schema["items"], root, f"{path}[{i}]", errors)


# --- project-side input ------------------------------------------------------
def load_schema() -> dict:
    try:
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BrainError(f"manifest schema unreadable ({SCHEMA_PATH}): {exc}")


def determinism_state(root: Path) -> tuple[str, str]:
    """('enabled'|'off'|'not-declared'|'unknown', detail) from game-manifest.json.

    An absent `determinism.enabled` means OFF: a project that never declared a
    policy cannot be broken retroactively, so the rule is opt-in. A value that
    is present and not a boolean cannot be read as a policy and raises: the
    brain refuses to guess whether a run is comparable.
    """
    manifest_path = root / "game-manifest.json"
    if not manifest_path.exists():
        return "unknown", "no game-manifest.json in this root"
    try:
        doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BrainError(f"game-manifest.json is unreadable: {exc}")
    if not isinstance(doc, dict):
        raise BrainError("game-manifest.json is not a JSON object")
    block = doc.get("determinism")
    if block is None:
        return "not-declared", "determinism.enabled is not declared (rule off)"
    if not isinstance(block, dict) or not isinstance(block.get("enabled"), bool):
        raise BrainError("game-manifest.json determinism.enabled is not a "
                         "boolean - the rule cannot read that policy")
    if block["enabled"]:
        return "enabled", "determinism.enabled is true"
    return "off", "determinism.enabled is false"


def session_errors(manifest: dict, det: str) -> list[str]:
    """The rules a static subset cannot express (session-01, session-02)."""
    errors: list[str] = []
    if "capture" in manifest:
        stream = manifest["capture"].get("stream_id")
        if not isinstance(stream, str) or not stream.strip():
            errors.append("capture: stream_id is required whenever the capture "
                          "block is declared")
    if manifest.get("kind") == "play":
        if det == "unknown":
            errors.append("kind play: refused - game-manifest.json is absent in "
                          "this root, so determinism cannot be read")
        elif det == "enabled":
            seed = manifest.get("seed")
            if not isinstance(seed, str) or not seed.strip():
                errors.append("kind play: refused - determinism.enabled is true "
                              "and the manifest carries no non-empty seed")
    return errors


# --- advisory assembly -------------------------------------------------------
def _one_line(text, limit: int = ADVICE_TEXT_LIMIT) -> str:
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= limit else flat[:limit - 3] + "..."


def registry_hits(root: Path, scope: list[str] | None
                  ) -> tuple[list[dict] | None, str]:
    """Unresolved registry entries overlapping the session scope.

    Merged bundled + project overlay (gate_overlay), so a consumer's registry
    is visible. `.guardrailsignore` filters this ADVICE only - never the hard
    rule (you cannot annotate away a missing seed). An empty merged registry
    is unknown, not "no failures": the bundled baseline shipping zero entries
    means nothing was read.
    """
    entries, _owner = gate_overlay.resolve_registry(root)
    if not entries:
        return None, "no failure-registry entries readable (bundled + overlay)"
    ignore = gate_common.load_ignore_patterns(root)
    hits: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("status") in ("resolved",
                                                                  "deprecated"):
            continue
        paths = [p for p in (entry.get("affected_files") or []) if isinstance(p, str)]
        globs = [g for g in (entry.get("file_glob") or []) if isinstance(g, str)]
        files = [f for f in paths + globs
                 if not gate_common.is_ignored(root / f, root, ignore)]
        if not files:
            continue
        if scope is None or any(gate_common.glob_matches(f, scope) for f in files):
            hits.append(entry)
    hits.sort(key=lambda e: str(e.get("failure_id", "")))
    detail = ("no scope declared - every entry counted"
              if scope is None else "scope " + ", ".join(scope))
    return hits, detail


def gap_block(root: Path, report_path: Path) -> dict:
    """Read the gap scanner's JSON - never a second inventory (session-05).

    `count` is the number `--fail-on-gaps` acts on (unspaced + partially
    tracked + uncovered ids); CLAIMED-BUT-ABSENT never contributes. Only a
    report describing THIS root counts: a report from another tree is unknown,
    not this session's number.
    """
    block: dict = {"state": "unknown", "count": None, "worst": None,
                   "reason": "", "source": str(report_path)}
    if not report_path.exists():
        block["reason"] = f"no gap report at {report_path}"
        return block
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        block["reason"] = f"gap report unreadable: {exc}"
        return block
    summary = report.get("summary") if isinstance(report, dict) else None
    if not isinstance(summary, dict) or not all(
            isinstance(summary.get(key), int) for key in GAP_SUMMARY_KEYS):
        block["reason"] = "gap report is not the scanner's --json shape"
        return block
    report_root = report.get("root")
    if isinstance(report_root, str):
        try:
            same_root = Path(report_root).resolve() == root.resolve()
        except OSError:
            same_root = False
        if not same_root:
            block["reason"] = f"gap report describes {report_root}, not this root"
            return block
    block["state"] = "known"
    block["count"] = sum(summary[key] for key in GAP_SUMMARY_KEYS)
    unspaced = (report.get("inventory") or {}).get("unspaced") or []
    if unspaced and isinstance(unspaced[0], dict):
        block["worst"] = unspaced[0].get("capability")
        block["worst_evidence"] = unspaced[0].get("evidence")
    return block


def gap_lines(block: dict) -> list[str]:
    if block["state"] != "known":
        return [f"  worst-tracked gaps: unknown - {block['reason']}"]
    lines = [f"  worst-tracked gaps: {block['count']}"]
    if block["worst"]:
        evidence = block.get("worst_evidence")
        suffix = f" [{evidence}]" if evidence else ""
        lines.append(f"  worst: {block['worst']}{suffix}")
    return lines


def advisory(manifest: dict, root: Path, det: tuple[str, str],
             gap: dict) -> list[str]:
    """The kind-filtered advisory block (session-03)."""
    kind = manifest["kind"]
    who = manifest.get("opened_by", "unknown")
    lines = [f"aiggp session start: {kind} session in {manifest['game']} ({who})"]
    if kind == "work":
        phase = manifest.get("phase")
        if phase:
            lines.append(f"  phase: {phase}")
            lines.append("  phase gates: unknown - the phase matrix is planned "
                         "(game-matrix-01), not implemented in this tree")
        else:
            lines.append("  phase: unknown - no phase claimed, no gates listed")
    lines.append(f"  determinism: {det[0]} - {det[1]}")
    hits, detail = registry_hits(root, manifest.get("scope"))
    if hits is None:
        lines.append(f"  registry hits: unknown - {detail}")
    else:
        lines.append(f"  registry hits ({detail}): {len(hits)}")
        for entry in hits[:REGISTRY_ADVICE_LIMIT]:
            lines.append("    {} [{}] {}".format(
                entry.get("failure_id", "?"), entry.get("severity", "?"),
                _one_line(entry.get("error_message"))))
        if len(hits) > REGISTRY_ADVICE_LIMIT:
            lines.append(f"    ... {len(hits) - REGISTRY_ADVICE_LIMIT} more "
                         "(see .guardrails/failure-registry.jsonl)")
    if kind == "work":
        if (root / PRE_WORK_REL).exists():
            lines.append(f"  pre-work check: {PRE_WORK_REL}")
        else:
            lines.append(f"  pre-work check: absent ({PRE_WORK_REL} not in "
                         "this root)")
        lines.extend(gap_lines(gap))
    else:
        lines.append("  screen inventory: not evaluated at session start - run "
                     "scripts/scene_inventory.py (the Godot hook owns this block)")
    capture = manifest.get("capture")
    if isinstance(capture, dict) and capture.get("stream_id"):
        lines.append(f"  capture: stream {capture['stream_id']} - inspect with "
                     "get_frame, semantic_diff, and the gate report")
    else:
        lines.append("  capture: none")
    return lines


# --- the append-only log -----------------------------------------------------
def append_session(root: Path, manifest: dict) -> Path:
    """One immutable row per accepted session; duplicates append too (history,
    not a set). Canonical key order so two identical manifests produce
    identical bytes."""
    log_path = root / LOG_REL
    log_path.parent.mkdir(parents=True, exist_ok=True)
    row = json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True)
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(row + "\n")
    return log_path


# --- entry point -------------------------------------------------------------
def read_manifest(args) -> tuple[dict | None, list[str]]:
    if args.stdin:
        raw = sys.stdin.read()
    elif args.manifest is not None:
        try:
            raw = Path(args.manifest).read_text(encoding="utf-8")
        except OSError as exc:
            raise BrainError(f"manifest unreadable: {exc}")
    else:
        raise BrainError("no manifest supplied - pass --stdin or --manifest PATH")
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, [f"manifest does not parse as JSON: {exc}"]
    if not isinstance(manifest, dict):
        return None, ["manifest is not a JSON object"]
    return manifest, []


def refuse(errors: list[str], as_json: bool) -> int:
    for error in errors:
        print(f"game-session-start: refused - {error}", file=sys.stderr)
    if as_json:
        print(json.dumps({"schema": "aiggp.session-start-result/v1",
                          "verdict": "refused", "errors": errors}, indent=1))
    return EXIT_REFUSED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="gameSessionStart brain for aiggp.session/v1")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--stdin", action="store_true",
                        help="read the manifest JSON from stdin")
    source.add_argument("--manifest", type=Path,
                        help="read the manifest JSON from this file")
    parser.add_argument("--root", type=Path, default=None,
                        help="project root (default: the layout contract)")
    parser.add_argument("--gap-report", type=Path, default=None,
                        help="spec-gap scanner --json report (default: "
                             ".guardrails/spec-gap-report.json)")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="print the machine result instead of the block")
    args = parser.parse_args(argv)

    try:
        root = Path(args.root or gate_common.project_root()).resolve()
        if not root.is_dir():
            raise BrainError(f"project root is not a directory: {root}")
        schema = load_schema()
        manifest, errors = read_manifest(args)
        if manifest is not None:
            validate(manifest, schema, schema, "manifest", errors)
        if errors:
            return refuse(errors, args.as_json)
        det = determinism_state(root)
        errors = session_errors(manifest, det[0])
        if errors:
            return refuse(errors, args.as_json)
        gap = gap_block(root, Path(args.gap_report or (root / GAP_REPORT_REL)).resolve())
        lines = advisory(manifest, root, det, gap)
        log_path = append_session(root, manifest)
    except BrainError as exc:
        print(f"game-session-start: cannot say - {exc}", file=sys.stderr)
        return EXIT_CANNOT_SAY
    except OSError as exc:
        print(f"game-session-start: cannot say - {exc}", file=sys.stderr)
        return EXIT_CANNOT_SAY

    if args.as_json:
        print(json.dumps({
            "schema": "aiggp.session-start-result/v1",
            "verdict": "accepted",
            "advisory": lines,
            "determinism": {"state": det[0], "detail": det[1]},
            "gap": {key: gap[key] for key in
                    ("state", "count", "worst", "reason", "source")},
            "log": str(log_path.relative_to(root)),
        }, indent=1))
    else:
        for line in lines:
            print(line)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
