#!/usr/bin/env python3
"""Spec traceability gate: every openspec requirement ID needs a `// spec: <id>`
marker in a source file. Modes: advisory (exit 0, report) / blocking (exit 1).
Per-spec override via openspec/gate-config.json: {"specs": {"<capability>": "blocking"}}.
Exit codes: 0 pass, 1 uncovered in blocking mode, 2 usage/error."""
import argparse
import json
import re
import sys
from pathlib import Path

REQ_ID = re.compile(r"<!--\s*id:\s*([a-z0-9-]+)\s*-->")
MARKER = re.compile(r"//\s*spec:\s*([a-z0-9-]+)")
SCAN_EXTS = {".rs", ".py", ".mjs", ".js", ".ts"}
SCAN_SKIP = {"target", "node_modules", ".git", "openspec", ".devgate"}


def load_config(root: Path) -> dict:
    cfg_path = root / "openspec" / "gate-config.json"
    if not cfg_path.exists():
        return {"default_mode": "advisory", "specs": {}}
    return json.loads(cfg_path.read_text())


def collect_requirements(root: Path) -> dict:
    """capability -> {req_id: spec_path}"""
    out = {}
    specs_dir = root / "openspec" / "specs"
    if not specs_dir.is_dir():
        return out
    for spec in sorted(specs_dir.glob("*/spec.md")):
        capability = spec.parent.name
        ids = REQ_ID.findall(spec.read_text())
        out.setdefault(capability, {})
        for rid in ids:
            out[capability][rid] = spec
    return out


def collect_markers(root: Path) -> set:
    markers = set()
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in SCAN_EXTS:
            continue
        if any(part in SCAN_SKIP for part in path.parts):
            continue
        try:
            markers.update(MARKER.findall(path.read_text(errors="ignore")))
        except OSError:
            continue
    return markers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", action="store_true",
                        help="print per-requirement coverage detail")
    args = parser.parse_args()
    root = args.root.resolve()

    try:
        config = load_config(root)
        requirements = collect_requirements(root)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"spec-traceability: config/parse error: {exc}", file=sys.stderr)
        return 2

    if not requirements:
        print("spec-traceability: no specs found under openspec/specs/")
        return 2

    markers = collect_markers(root)
    default_mode = config.get("default_mode", "advisory")
    per_spec = config.get("specs", {})

    blocking_failures = []
    for capability, reqs in requirements.items():
        mode = per_spec.get(capability, default_mode)
        for rid in reqs:
            covered = rid in markers
            if args.report:
                state = "covered" if covered else "UNCOVERED"
                print(f"{rid}: {state} (mode={mode})")
            if not covered and mode == "blocking":
                blocking_failures.append(rid)

    total = sum(len(r) for r in requirements.values())
    covered_count = len(markers & set(rid for r in requirements.values() for rid in r))
    uncovered = total - covered_count
    print(f"spec-traceability: {covered_count}/{total} requirements covered")

    if blocking_failures:
        print(f"spec-traceability: BLOCKING failures: {', '.join(blocking_failures)}")
        return 1
    if uncovered:
        print(f"spec-traceability: advisory — {uncovered} uncovered requirement(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
