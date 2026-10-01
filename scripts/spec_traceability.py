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
found" - a gate that misdescribes what it looked at cannot be trusted.

Coverage discovery is shared with the gap scanner via scripts/lib/
spec_discovery.py (SGA-05) — this script holds no regex of its own."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from spec_discovery import (  # noqa: E402
    collect_markers,
    collect_requirements,
    find_spec_files,
)


def load_config(root: Path) -> dict:
    cfg_path = root / "openspec" / "gate-config.json"
    if not cfg_path.exists():
        return {"default_mode": "advisory", "specs": {}}
    return json.loads(cfg_path.read_text(encoding="utf-8"))


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
            recorded = json.loads(ratchet_path.read_text(encoding="utf-8")) \
                if ratchet_path.exists() else {}
        except (OSError, json.JSONDecodeError) as exc:
            print(f"spec-traceability: cannot read ratchet floor "
                  f"{ratchet_path}: {exc}", file=sys.stderr)
            return 2
        floor = recorded.get("min_covered")
        if floor is None:
            ratchet_path.parent.mkdir(parents=True, exist_ok=True)
            ratchet_path.write_text(json.dumps(
                {"min_covered": covered_count}, indent=1) + "\n", encoding="utf-8")
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
                    {"min_covered": covered_count}, indent=1) + "\n", encoding="utf-8")
                print(f"spec-traceability: ratchet floor raised to "
                      f"{covered_count}")
            else:
                print(f"spec-traceability: coverage grew above the floor "
                      f"({floor}) — raise it with --update-ratchet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
