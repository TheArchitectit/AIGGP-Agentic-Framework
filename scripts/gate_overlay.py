#!/usr/bin/env python3
"""gate_overlay.py — merge a project's .guardrails/ overlay over DevGate's
bundled rules/registry, so a game can ADD its own rules without forking the
baseline.

This is the shared resolver behind the "submodule + thin overlay" layout:

    <project>/
      .devgate/            <- DevGate submodule (the baseline, shared by every game)
        .guardrails/prevention-rules/{pattern-rules,semantic-rules}.json
        .guardrails/failure-registry.jsonl
      .guardrails/         <- THIS project's overlay (its SI-*/game-specific delta)
        prevention-rules/{pattern-rules,semantic-rules}.json
        failure-registry.jsonl

Default resolution merges BOTH, de-duplicated by id with the overlay winning on
an id collision (so a game can retune severity or fix a false-positive on a
baseline rule without editing the submodule). New overlay-only ids append.

An explicit path — via --rules / --registry or the PREVENTION_RULES_PATH /
FAILURE_REGISTRY_PATH env var — collapses to a SINGLE source, no merge. That
preserves the override semantics the tests and CI already rely on: "I told you
exactly which file to read, don't second-guess it."

Each merged entry is tagged with a "_source" of "devgate" or "project" so the
gates that validate git-resolved fields (fix_commit) can check the entry against
the repo that actually owns it, instead of assuming the current project's
history contains upstream SHAs.
"""
from __future__ import annotations

import json
from pathlib import Path

SOURCE_DEVGATE = "devgate"
SOURCE_PROJECT = "project"


def devgate_root() -> Path:
    """The submodule root — the parent of the scripts/ dir this lives in."""
    return Path(__file__).resolve().parent.parent


def _read_json_rules(path: Path, kind: str) -> list[dict]:
    """Return the rule dicts from a *.json rules file ([] if absent/invalid).

    Each entry is tagged with _kind ("pattern" | "semantic") so callers that
    distinguish rule types (regression_check.py's rule_type) can tell after a
    merge which file an entry came from.
    """
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    rules = data.get("rules", [])
    if not isinstance(rules, list):
        return []
    for r in rules:
        r["_kind"] = kind
    return rules


def merge_by_id(bundled: list[dict], overlay: list[dict], id_key: str) -> list[dict]:
    """Overlay wins on id collision (retained position from bundled), new ids append."""
    out: list[dict] = []
    index: dict[str, int] = {}
    for entry in bundled:
        eid = entry.get(id_key)
        if eid is None:
            out.append(entry)
            continue
        index[eid] = len(out)
        out.append(entry)
    for entry in overlay:
        eid = entry.get(id_key)
        if eid is not None and eid in index:
            out[index[eid]] = entry  # replace in place, preserving order
        else:
            if eid is not None:
                index[eid] = len(out)
            out.append(entry)
    return out


def _tag(entries: list[dict], source: str) -> list[dict]:
    for e in entries:
        e["_source"] = source
    return entries


RULE_FILES = (("pattern-rules.json", "pattern"), ("semantic-rules.json", "semantic"))


def _collect_rule_files(rules_dir: Path, source: str) -> list[dict]:
    out: list[dict] = []
    for name, kind in RULE_FILES:
        for r in _read_json_rules(rules_dir / name, kind):
            r["_source"] = source
            out.append(r)
    return out


def resolve_rules(project_root: Path, explicit: Path | None = None) -> list[dict]:
    """Merged, ordered rule dicts (pattern + semantic) from pattern-rules.json
    and semantic-rules.json.

    explicit=None  -> merge bundled .devgate/.guardrails/prevention-rules/ with
                      the project overlay <project_root>/.guardrails/prevention-rules/
    explicit=<path> -> read ONLY <path>/prevention-rules/*.json (or <path> if it
                      already points at the prevention-rules dir), no merge.

    Every returned dict carries _source ("devgate"|"project") and _kind
    ("pattern"|"semantic"); consumers apply their own enabled/severity/regex
    filters on top, exactly as before the merge existed.
    """
    dg = devgate_root()
    if explicit is not None:
        rules_dir = explicit if (explicit / "pattern-rules.json").exists() else explicit / "prevention-rules"
        return _collect_rule_files(rules_dir, SOURCE_DEVGATE)

    base = dg / ".guardrails" / "prevention-rules"
    over = project_root / ".guardrails" / "prevention-rules"
    if not over.exists():
        return _collect_rule_files(base, SOURCE_DEVGATE)  # unchanged legacy behaviour
    return merge_by_id(
        _collect_rule_files(base, SOURCE_DEVGATE),
        _collect_rule_files(over, SOURCE_PROJECT),
        "rule_id",
    )


def resolve_registry(
    project_root: Path,
    explicit: Path | None = None,
    statuses: tuple[str, ...] | None = None,
) -> tuple[list[dict], dict[str, Path]]:
    """(entries, owner_by_id). entries is the merged JSONL registry; owner_by_id
    maps failure_id -> the repo root whose git history owns its fix_commit.

    explicit=None -> merge bundled + project overlay.
    explicit=<path> -> read only that file (owner = project_root).
    statuses=None -> return every entry; otherwise keep only entries whose
                     "status" is in the tuple (SCANNED_STATUSES for the pattern
                     gate; None for the registry hygiene gate, which must see
                     deprecated/wrong-status entries to flag them).
    """
    dg = devgate_root()
    if explicit is not None:
        entries = _read_jsonl(explicit)
        _tag(entries, SOURCE_DEVGATE)
        owner = {e["failure_id"]: project_root for e in entries if e.get("failure_id")}
    else:
        base = dg / ".guardrails" / "failure-registry.jsonl"
        over = project_root / ".guardrails" / "failure-registry.jsonl"
        if not over.exists():
            entries = _read_jsonl(base)
            _tag(entries, SOURCE_DEVGATE)
            owner = {e["failure_id"]: dg for e in entries if e.get("failure_id")}
        else:
            entries = merge_by_id(_read_jsonl(base), _read_jsonl(over), "failure_id")
            owner = {}
            for e in entries:
                if e.get("failure_id"):
                    owner[e["failure_id"]] = dg if e.get("_source") == SOURCE_DEVGATE else project_root
    if statuses is not None:
        entries = [e for e in entries if e.get("status") in statuses]
        owner = {k: v for k, v in owner.items() if k in {e.get("failure_id") for e in entries}}
    return entries, owner


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries
