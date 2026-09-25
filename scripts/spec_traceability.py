#!/usr/bin/env python3
"""Spec traceability gate: every openspec requirement ID needs a spec marker
(`// spec: <id>` or `# spec: <id>` — both comment styles count) in a source
file. Modes: advisory (exit 0, report) / blocking (exit 1).
Per-spec override via openspec/gate-config.json: {"specs": {"<capability>": "blocking"}}.
Exit codes: 0 pass, 1 uncovered in blocking mode, 2 usage/config error.

Spec discovery covers BOTH standard OpenSpec layouts:
  openspec/specs/<capability>/spec.md          (published specs)
  openspec/changes/<change>/specs/**/*.md      (change packages, archive/ skipped)
Requirement IDs use the <!-- id: ... --> marker; heading-only specs are
reported as "0 requirement IDs in the supported format", never as "no specs
found" - a gate that misdescribes what it looked at cannot be trusted."""
import argparse
import json
import re
import sys
from pathlib import Path

REQ_ID = re.compile(r"<!--\s*id:\s*([a-z0-9-]+)\s*-->")
# One marker line may carry several IDs: `// spec: a-01, b-02, c-03`.
# Anchored to the ID shape and comma-separated so a trailing comment
# (`// spec: a-01 -- why`) is not swallowed into the match. Both `//`
# (C-family, JS) and `#` (Python, shell) comment prefixes are accepted —
# H6: the `//`-only grammar locked Python consumers out of blocking mode.
# `.sh` files use the same `# // spec:` shape (see
# scripts/specs-validate-negative-control.sh); the extension list below is
# widened to match the shipped gate surface.
MARKER = re.compile(r"(?://|#)\s*spec:[ \t]*([a-z0-9-]+(?:[ \t]*,[ \t]*[a-z0-9-]+)*)")
ID = re.compile(r"[a-z0-9-]+")
SCAN_EXTS = {".rs", ".py", ".mjs", ".js", ".ts", ".sh", ".zig"}
SCAN_SKIP = {"target", "node_modules", ".git", "openspec", ".devgate"}
ID = re.compile(r"[a-z0-9-]+")
# Shell scripts are part of the shipped gate surface: the specs negative
# control that proves strict validation can refuse malformed material lives in
# a .sh file. Without .sh here, a marker in that file is silently invisible and
# its requirement reads UNCOVERED — coverage that looks asserted in the source
# but is never counted.
SCAN_EXTS = {".rs", ".py", ".mjs", ".js", ".ts", ".sh", ".zig"}
SCAN_SKIP = {"target", "node_modules", ".git", "openspec", ".devgate"}


def load_config(root: Path) -> dict:
    cfg_path = root / "openspec" / "gate-config.json"
    if not cfg_path.exists():
        return {"default_mode": "advisory", "specs": {}}
    return json.loads(cfg_path.read_text())


def find_spec_files(root: Path) -> list[Path]:
    """All spec files in both standard OpenSpec layouts.

    openspec/specs/<capability>/spec.md plus openspec/changes/<change>/specs/**/*.md,
    skipping archived changes (their requirements already live, or are being
    moved, under openspec/specs/).
    """
    files = sorted((root / "openspec" / "specs").glob("*/spec.md"))
    changes = root / "openspec" / "changes"
    if changes.is_dir():
        for spec in sorted(changes.glob("*/specs/**/*.md")):
            if "archive" not in spec.relative_to(changes).parts:
                files.append(spec)
    return files


def collect_requirements(root: Path) -> dict:
    """capability -> {req_id: spec_path}, across both OpenSpec layouts."""
    out = {}
    for spec in find_spec_files(root):
        # specs/<cap>/spec.md -> capability dir; flat change specs/<file>.md
        # -> file stem (DevGate's own change packages use that flat layout).
        capability = spec.parent.name if spec.name == "spec.md" else spec.stem
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
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        for group in MARKER.findall(text):
            markers.update(ID.findall(group))
    return markers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", action="store_true",
                        help="print per-requirement coverage detail")
    parser.add_argument("--ratchet", action="store_true",
                        help="fail when covered requirements drop below the "
                             "recorded floor (.guardrails/"
                             "traceability-ratchet.json, {\"min_covered\": "
                             "N}). Advisory-only coverage can silently "
                             "shrink; the floor makes regression visible "
                             "while unbuilt capabilities stay advisory.")
    parser.add_argument("--update-ratchet", action="store_true",
                        help="with --ratchet: raise the recorded floor to "
                             "the current covered count")
    args = parser.parse_args()
    root = args.root.resolve()

    try:
        config = load_config(root)
        requirements = collect_requirements(root)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"spec-traceability: config/parse error: {exc}", file=sys.stderr)
        return 2

    total_ids = sum(len(r) for r in requirements.values())
    if total_ids == 0:
        spec_files = find_spec_files(root)
        if spec_files:
            print(f"spec-traceability: found {len(spec_files)} spec file(s) under "
                  "openspec/specs/ and openspec/changes/*/specs/ but 0 requirement IDs "
                  "in the supported <!-- id: name --> format. Add id markers to the "
                  "requirements this gate should track, or it stays a config error (exit 2).")
        else:
            print("spec-traceability: no spec files found under openspec/specs/ or "
                  "openspec/changes/*/specs/ (searched both OpenSpec layouts)")
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

    total = total_ids
    covered_count = len(markers & set(rid for r in requirements.values() for rid in r))
    uncovered = total - covered_count
    print(f"spec-traceability: {covered_count}/{total} requirements covered")

    if blocking_failures:
        print(f"spec-traceability: BLOCKING failures: {', '.join(blocking_failures)}")
        return 1
    if uncovered:
        print(f"spec-traceability: advisory — {uncovered} uncovered requirement(s)")

    if args.ratchet:
        # fw-tr-01: the covered-count floor. A drop below the floor means
        # markers were deleted (or specs added without implementation) — a
        # regression the advisory mode alone would wave through.
        ratchet_path = root / ".guardrails" / "traceability-ratchet.json"
        try:
            recorded = json.loads(ratchet_path.read_text()) \
                if ratchet_path.exists() else {}
        except (OSError, json.JSONDecodeError) as exc:
            print(f"spec-traceability: cannot read ratchet floor "
                  f"{ratchet_path}: {exc}", file=sys.stderr)
            return 2
        floor = recorded.get("min_covered")
        if floor is None:
            ratchet_path.parent.mkdir(parents=True, exist_ok=True)
            ratchet_path.write_text(json.dumps(
                {"min_covered": covered_count}, indent=1) + "\n")
            print(f"spec-traceability: ratchet floor initialized at "
                  f"{covered_count} ({ratchet_path})")
        elif covered_count < floor:
            print(f"spec-traceability: RATCHET REGRESSION — {covered_count} "
                  f"covered is below the floor of {floor}. Markers were "
                  f"removed or specs outgrew the implementation.")
            return 1
        elif covered_count > floor:
            if args.update_ratchet:
                ratchet_path.write_text(json.dumps(
                    {"min_covered": covered_count}, indent=1) + "\n")
                print(f"spec-traceability: ratchet floor raised to "
                      f"{covered_count}")
            else:
                print(f"spec-traceability: coverage grew above the floor "
                      f"({floor}) — raise it with --update-ratchet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
