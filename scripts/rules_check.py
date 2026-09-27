#!/usr/bin/env python3
# spec: rule-truth-01
"""rules_check.py — rules-hygiene gate (rule-truth-01, design D7).

An enabled rule with no executing checker is the silent-success shape this
framework exists to catch: docs claim coverage, and the gate that would prove
it runs nothing. This check closes that:

  1. every enabled rule in semantic-rules.json has a checker registered in
     the scanner — asked via `semantic-scan.mjs --list-checkers`, the
     scanner's own executable truth, not a grep of its source;
  2. pattern-rules.json validates against pattern-rules.schema.json (a local
     Draft-07 subset: type/required/properties/items/enum/pattern/
     additionalProperties/$ref — enough for this schema, stdlib only);
  3. no enabled rule lacks a message or a valid severity.

Exit codes:
    0  — clean
    1  — findings, including "cannot verify": when the checker list cannot be
         read (node missing, scanner broken) the check FAILS rather than
         skipping, because an unverifiable "enabled ⇒ enforced" is exactly the
         claim this gate exists to make.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

DEVGATE_ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = DEVGATE_ROOT / ".guardrails" / "prevention-rules"
PATTERN_RULES = RULES_DIR / "pattern-rules.json"
PATTERN_SCHEMA = RULES_DIR / "pattern-rules.schema.json"
SEMANTIC_RULES = RULES_DIR / "semantic-rules.json"
SEVERITIES = {"critical", "error", "warning", "info"}


def load_json(path: Path, findings: list[str]):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        findings.append(f"rules-check: {path.name} missing — the bundled rules "
                        f"file ships with the checkout ({path})")
        return None
    except json.JSONDecodeError as exc:
        findings.append(f"rules-check: {path.name} does not parse: {exc}")
        return None


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


def validate(instance, schema: dict, root: dict, path: str, findings: list[str]) -> None:
    """Draft-07 subset sufficient for pattern-rules.schema.json."""
    if "$ref" in schema:
        validate(instance, _resolve_ref(schema["$ref"], root), root, path, findings)
        return
    want = schema.get("type")
    if want:
        types = want if isinstance(want, list) else [want]
        if not any(_is_type(instance, t) for t in types):
            findings.append(f"rules-check: {path}: expected type {types}, "
                            f"got {type(instance).__name__}")
            return
    if "enum" in schema and instance not in schema["enum"]:
        findings.append(f"rules-check: {path}: {instance!r} not in enum {schema['enum']}")
    if "pattern" in schema and isinstance(instance, str):
        if not re.search(schema["pattern"], instance):
            findings.append(f"rules-check: {path}: {instance!r} does not match "
                            f"pattern {schema['pattern']!r}")
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                findings.append(f"rules-check: {path}: missing required field '{key}'")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    findings.append(f"rules-check: {path}: unknown field '{key}'")
        for key, sub in props.items():
            if key in instance:
                validate(instance[key], sub, root, f"{path}.{key}", findings)
    if isinstance(instance, list) and "items" in schema:
        for i, item in enumerate(instance):
            validate(item, schema["items"], root, f"{path}[{i}]", findings)


def registered_checkers() -> list[str] | None:
    """Checker ids from the scanner itself; None = cannot verify."""
    try:
        result = subprocess.run(
            ["node", str(DEVGATE_ROOT / "scripts" / "semantic-scan.mjs"),
             "--list-checkers"],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, list) else None


def main() -> int:
    findings: list[str] = []

    pattern_doc = load_json(PATTERN_RULES, findings)
    schema_doc = load_json(PATTERN_SCHEMA, findings)
    if pattern_doc is not None and schema_doc is not None:
        validate(pattern_doc, schema_doc, schema_doc, "pattern-rules", findings)

    semantic_doc = load_json(SEMANTIC_RULES, findings)
    if semantic_doc is not None:
        enabled = []
        for rule in semantic_doc.get("rules", []):
            rid = rule.get("rule_id", "?")
            if not rule.get("enabled"):
                continue
            enabled.append(rid)
            message = rule.get("message")
            if not isinstance(message, str) or not message.strip():
                findings.append(f"rules-check: enabled rule {rid} has no message")
            if rule.get("severity") not in SEVERITIES:
                findings.append(f"rules-check: enabled rule {rid} has invalid "
                                f"severity {rule.get('severity')!r}")

        checkers = registered_checkers()
        if checkers is None:
            findings.append("rules-check: CANNOT VERIFY that enabled semantic "
                            "rules have checkers (node or semantic-scan.mjs "
                            "unavailable) — failing closed, not passing silently")
        else:
            for rid in enabled:
                if rid not in checkers:
                    findings.append(f"rules-check: enabled rule {rid} has no "
                                    f"registered checker in semantic-scan.mjs "
                                    f"(rule-truth-01)")

    for finding in findings:
        print(finding)
    if findings:
        print(f"rules-check: {len(findings)} finding(s)", file=sys.stderr)
        return 1
    print("rules-check: OK — every enabled rule has a registered checker; "
          "pattern rules validate against the schema")
    return 0


if __name__ == "__main__":
    sys.exit(main())
