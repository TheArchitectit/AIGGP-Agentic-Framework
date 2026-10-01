#!/usr/bin/env python3
# spec: sga-01
"""Spec gap scanner: mechanical inventory-vs-coverage for a repository.

Turns spec_traceability.py's exit-2 config refusal ("no spec universe")
into an actionable, ranked gap list — WITHOUT softening that refusal
(SGA-06) and WITHOUT authoring requirement prose (SGA-01: every row
carries a file:line evidence pointer into source that was read, or it
is not emitted).

Honesty rails, from the MergeKingdom work order (2026-09-29):
  1. no evidence pointer -> no row.
  2. --draft output is born `<!-- draft: unreviewed -->` and is excluded
     from every coverage count (SGA-02; enforced in spec_discovery).
  3. CLAIMED-BUT-ABSENT is a lead section, never a requirement, and never
     fails --fail-on-gaps.
  4. "looked and found nothing" is stated as such — an empty inventory
     exits 2 with `unknown scope (no anchors found)`, never a silent 0.
  5. exits follow the secret-scan family: 0 no gaps · 1 gaps under
     --fail-on-gaps · 2 scanner unusable / config error. NOTE the contrast
     with game_session_start.py's inverted `2 refused / 1 cannot say` —
     documented, do not unify.

Coverage discovery is imported from scripts/lib/spec_discovery.py (SGA-05)
so this scanner and the traceability gate cannot report different numbers
for the same tree.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from spec_discovery import collect_markers, collect_requirements, find_spec_files  # noqa: E402

GD_CODE_START = re.compile(r"^(const|var|signal|enum|func|static func|@export)\b")
FUNC_DEF = re.compile(r"^static func |^func ")
CONST_DECL = re.compile(r"^const\s+([A-Z][A-Z0-9_]*)")
MARKER_IN_FILE = re.compile(r"(?://|#)\s*spec:")

# Inventory roots, game-shaped (the fleet's dominant repo class; a
# general-purpose repo yields a smaller inventory — never "nothing to
# spec" unless it truly found no anchors, SGA-04).
INVENTORY_DIRS = ("src/autoload", "src/core", "src/models", "src/ui",
                  "src/scenes", "data")


def kebab(stem: str) -> str:
    return stem.replace("_", "-")


def file_anchor(path: Path, root: Path) -> dict:
    """Evidence pointer: repo-relative path, first code line..last line."""
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    first = next((i + 1 for i, ln in enumerate(lines) if GD_CODE_START.match(ln)), 1)
    return {"path": str(path.relative_to(root)), "line": first,
            "end_line": len(lines), "lines": len(lines)}


def build_inventory(root: Path) -> list[dict]:
    """Capability candidates named from files that exist — never invented."""
    caps = {}
    for d in INVENTORY_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix == ".gd":
                stem = path.stem
                if stem in ("main",):  # scene entry points are not capabilities
                    continue
                cap = kebab(stem)
                caps.setdefault(cap, {"capability": cap, "anchors": [],
                                      "markers": 0, "funcs": 0})
                caps[cap]["anchors"].append(file_anchor(path, root))
                text = path.read_text(encoding="utf-8", errors="ignore")
                caps[cap]["markers"] += len(MARKER_IN_FILE.findall(text))
                caps[cap]["funcs"] += len(FUNC_DEF.findall(text))
            elif path.suffix == ".json" and base.name == "data":
                cap = kebab(path.stem)
                caps.setdefault(cap, {"capability": cap, "anchors": [],
                                      "markers": 0, "funcs": 0})
                caps[cap]["anchors"].append(file_anchor(path, root))
    return list(caps.values())


def spec_capabilities(root: Path) -> set:
    """Capability names the coverage side actually has spec files for."""
    out = set()
    for spec in find_spec_files(root):
        out.add(kebab(spec.parent.name if spec.name == "spec.md" else spec.stem))
    return out


def _src_blob(root: Path) -> str:
    parts = []
    for path in sorted((root / "src").rglob("*.gd")) if (root / "src").is_dir() else []:
        parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


TRACK_EMIT = re.compile(r'track_event\(\s*"([a-z_][a-z0-9_]*)"')


def claimed_but_absent(root: Path) -> list[dict]:
    """§C leads: mechanical, evidence-pointed claims with no code.

    Two classes, both verified as IDENTIFIER ABSENCE in a defined search
    surface — never behavior inference. Deliberately dropped after the
    first testbed run: `signal-orphan` (a signal with no textual listener
    is NOT provably dead — Godot binds via .tscn ConnectSignal and via
    dynamic access, and this class re-emitted GAPS.md §E's retired
    production_ready lie) and prose `doc-claim` (backtick tokens in docs
    are names, not claims; the harvest picked up the fixture's own
    strikethrough §E text and file names). Under-claiming is honest;
    these two were not.

    Classes kept:
      const-dead    : `const NAME` defined with no other word-boundary
                      reference anywhere under src/
      event-claimed : a quest template's `"event"` value with no
                      `track_event("<ev>")` emitter anywhere under src/
                      (the work order's own dead-quest criterion)
    Every row cites the anchor that made the claim plus the swept surface.
    Rail 3: leads only — never promoted, never fails --fail-on-gaps.
    """
    rows = []
    if not (root / "src").is_dir():
        return rows
    blob = _src_blob(root)
    for path in sorted((root / "src").rglob("*.gd")):
        if "_scratch" in path.name:
            continue  # files the owner parked are not claim surfaces
        text = path.read_text(encoding="utf-8", errors="ignore")
        for i, ln in enumerate(text.splitlines()):
            m = CONST_DECL.match(ln.strip())
            if m and len(re.findall(rf"\b{m.group(1)}\b", blob)) <= 1:
                rows.append({"kind": "const-dead", "claim": m.group(1),
                             "evidence": f"{path.relative_to(root)}:{i + 1}",
                             "note": "defined; no other reference in src/"})
    emitters = set(TRACK_EMIT.findall(blob))
    if (root / "data").is_dir():
        for path in sorted((root / "data").glob("*.json")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for i, ln in enumerate(text.splitlines()):
                for ev in re.findall(r'"event"\s*:\s*"([a-z_][a-z0-9_]*)"', ln):
                    if ev not in emitters:
                        rows.append({"kind": "event-claimed", "claim": ev,
                                     "evidence": f"{path.relative_to(root)}:{i + 1}",
                                     "note": "quest template event; no "
                                             "track_event emitter in src/"})
    return rows


def scan(root: Path) -> dict:
    inventory = build_inventory(root)
    covered_caps = spec_capabilities(root)
    requirements = collect_requirements(root)
    markers = collect_markers(root)

    unspaced = [c for c in inventory
                if c["capability"] not in covered_caps and c["markers"] == 0]
    partially_tracked = [c for c in inventory
                         if c["capability"] not in covered_caps and c["markers"] > 0]
    for row in unspaced + partially_tracked:
        row["evidence"] = "; ".join(f"{a['path']}:{a['line']}-{a['end_line']}"
                                    for a in row["anchors"])
    # worst-tracked first: biggest untracked surface leads (the --ratchet
    # ethic — track the bottom of the pile, not the top).
    unspaced.sort(key=lambda c: -sum(a["lines"] for a in c["anchors"]))
    partially_tracked.sort(key=lambda c: -c["markers"])

    uncovered_ids = []
    for capability, reqs in sorted(requirements.items()):
        for rid, spec in sorted(reqs.items()):
            if rid not in markers:
                uncovered_ids.append({"id": rid, "capability": capability,
                                      "evidence": str(spec.relative_to(root))})
    total_ids = sum(len(r) for r in requirements.values())

    cba = claimed_but_absent(root)
    return {
        "root": str(root),
        "inventory": {
            "capabilities": len(inventory),
            "unspaced": unspaced,
            "partially_tracked": partially_tracked,
        },
        "coverage": {
            "requirement_ids": total_ids,
            "uncovered_ids": uncovered_ids,
        },
        "claimed_but_absent": cba,
        "summary": {
            "unspaced": len(unspaced),
            "partially_tracked": len(partially_tracked),
            "uncovered_ids": len(uncovered_ids),
            "claimed_but_absent": len(cba),
        },
    }


def human_table(report: dict) -> list[str]:
    s = report["summary"]
    out = [f"spec-gap-scan: {report['root']}",
           f"  capabilities={report['inventory']['capabilities']} "
           f"unspaced={s['unspaced']} partially_tracked={s['partially_tracked']} "
           f"uncovered_ids={s['uncovered_ids']}/{report['coverage']['requirement_ids']} "
           f"claimed_but_absent={s['claimed_but_absent']}"]
    if report["inventory"]["unspaced"]:
        out.append("  UNSPACED capabilities (worst-tracked first):")
        for c in report["inventory"]["unspaced"][:20]:
            out.append(f"    {c['capability']}  [{c['evidence']}]")
        if s["unspaced"] > 20:
            out.append(f"    … {s['unspaced'] - 20} more (see --json)")
    if report["coverage"]["uncovered_ids"]:
        out.append("  UNCOVERED requirement IDs (in specs, no source marker):")
        for r in report["coverage"]["uncovered_ids"][:20]:
            out.append(f"    {r['id']} ({r['capability']}) [{r['evidence']}]")
        if s["uncovered_ids"] > 20:
            out.append(f"    … {s['uncovered_ids'] - 20} more (see --json)")
    if report["claimed_but_absent"]:
        out.append("  CLAIMED-BUT-ABSENT — leads only, never requirements:")
        for r in report["claimed_but_absent"][:20]:
            out.append(f"    {r['kind']}: {r['claim']} [{r['evidence']}] — {r['note']}")
        if s["claimed_but_absent"] > 20:
            out.append(f"    … {s['claimed_but_absent'] - 20} more (see --json)")
    return out


def scaffold_stub(cap: dict, root: Path, draft: bool) -> Path:
    """Evidence stub at openspec/specs/<capability>/spec.md — never prose.

    --scaffold alone leaves the requirement slot EMPTY: no `<!-- id: -->`
    marker, because a generated stub cannot claim coverage it has not
    earned (SGA-01: the scanner does not author requirement prose).
    --draft additionally fills one slot with a generated ID born
    `<!-- draft: unreviewed -->` — spec_discovery excludes those from
    every coverage count until a human deletes the marker (SGA-02).
    Either way the stub keeps evidence anchors, and scaffold output can
    never include CLAIMED-BUT-ABSENT rows (rail 3).
    """
    path = root / "openspec" / "specs" / cap["capability"] / "spec.md"
    if path.exists():
        return path  # idempotent: re-running proposes nothing over existing specs
    evidence = "\n".join(f"- `{a['path']}:{a['line']}-{a['end_line']}` "
                         f"({a['lines']} lines)" for a in cap["anchors"])
    body = [f"# {cap['capability']}",
            "",
            "<!-- scaffolded by spec_gap_scan.py — evidence pointers only. -->",
            "",
            "## Purpose",
            "",
            "Capability anchors observed in source; this stub records where,",
            "not what. Fill the requirement slot(s) after reading the code.",
            "",
            "## Requirements",
            ""]
    if draft:
        rid = f"{cap['capability']}-gap-01"
        body += [f"### Requirement: {cap['capability']} SHALL implement "
                 "its evidenced behavior",
                 f"<!-- id: {rid} -->",
                 "<!-- draft: unreviewed -->",
                 "",
                 "TODO: reviewed prose is required before this counts (delete "
                 "the draft marker).",
                 "",
                 "#### Scenario: evidence",
                 "TODO: write the scenario.",
                 ""]
    else:
        body += ["### Requirement: TODO — unreviewed scaffold, no ID issued",
                 "(no requirement is claimed until a human authors it and "
                 "adds an id marker; the text of this stub must never contain "
                 "one, even as an example — discovery would parse it)",
                 ""]
    body += ["", "## Evidence", "", evidence, ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(body), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--fail-on-gaps", action="store_true")
    parser.add_argument("--scaffold", action="store_true",
                        help="write openspec/specs/<capability>/spec.md "
                             "stubs with evidence pointers (no prose) for "
                             "every UNSPACED capability")
    parser.add_argument("--draft", action="store_true",
                        help="with --scaffold: fill requirement slots marked "
                             "<!-- draft: unreviewed --> (excluded from counts)")
    args = parser.parse_args()
    root = args.root.resolve()

    if not root.is_dir():
        print(f"spec-gap-scan: not a directory: {root}", file=sys.stderr)
        return 2
    report = scan(root)
    if report["inventory"]["capabilities"] == 0:
        # SGA-04: an honest empty is NOT a pass — distinct wording, exit 2.
        print("spec-gap-scan: unknown scope (no anchors found) — looked at "
              f"{root}, no capability anchors under {', '.join(INVENTORY_DIRS)}",
              file=sys.stderr)
        return 2

    if args.draft and not args.scaffold:
        print("spec-gap-scan: --draft only applies with --scaffold",
              file=sys.stderr)
        return 2
    if args.scaffold:
        wrote = 0
        for cap in report["inventory"]["unspaced"]:
            # unspaced means no spec file exists by construction; scaffold_stub
            # still refuses to overwrite anything it finds there.
            path = scaffold_stub(cap, root, args.draft)
            wrote += 1
            print(f"spec-gap-scan: scaffold {'draft ' if args.draft else 'stub '}"
                  f"for {cap['capability']} -> "
                  f"{path.relative_to(root)}")
        print(f"spec-gap-scan: wrote {wrote}/{len(report['inventory']['unspaced'])}"
              f" scaffold{' drafts' if args.draft else ' stubs'}; scaffolds are "
              "not requirements — review before counting (SGA-02)")
        # Scaffold mode writes files and exits before the report/exit-code
        # path: the gap verdict belongs to the scan run that found them.
        return 0

    if args.as_json:
        print(json.dumps(report, indent=1))
    else:
        for line in human_table(report):
            print(line)

    gaps = report["summary"]["unspaced"] + report["summary"]["partially_tracked"] \
        + report["summary"]["uncovered_ids"]
    # claimed_but_absent NEVER contributes (rail 3).
    if args.fail_on_gaps and gaps:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
