#!/usr/bin/env python3
"""findings_to_spec.py — turn gate findings into openspec requirement skeletons.

The loop the gates feed:

    run gates -> findings (pattern-rule hits + failure-registry entries)
              -> THIS script: openspec/specs/<capability>/spec.md skeletons
              -> implement the fix, marking the source with `// spec: <id>`
              -> spec_traceability.py gates that every requirement is covered

Each finding becomes a requirement block in the openspec format the
traceability gate parses:

    ### Requirement: <title>
    <!-- id: <capability>-<source-slug> -->
    <SHALL statement derived from the finding>
    #### Scenario: ...
    - **WHEN** ... - **THEN** ...

Ids are kebab-case [a-z0-9-]+ to match REQ_ID in spec_traceability.py.
Re-running is idempotent: existing spec.md files are NEVER overwritten —
only findings that have no requirement yet are appended (matched by their
provenance line), so hand edits survive and the tool is safe to run in a loop.

Findings come from two merged sources (gate_overlay contract — bundled
.devgate baseline + project .guardrails/ overlay):

  * the failure registry (one requirement per entry, grouped by category)
  * optional live scanner output: pipe `guardrails-scan.mjs` stderr in with
    --stdin to fold current violations in as "unbacked" requirements.

Usage:
    python3 .devgate/scripts/findings_to_spec.py --capability save-system
    node .devgate/scripts/guardrails-scan.mjs 2>&1 | \\
        python3 .devgate/scripts/findings_to_spec.py --stdin --capability combat
    python3 .devgate/scripts/findings_to_spec.py --list   # what would be created
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_overlay  # noqa: E402

# Same layout contract as guardrails-scan.mjs: the project root is the directory
# CONTAINING .devgate/ — but standalone, DevGate is its own project.
dg = gate_overlay.devgate_root()
DEFAULT_ROOT = dg.parent if dg.name == ".devgate" else dg

# `[GUARDRAILS][warning] PREVENT-SI-002 src/x.rs:55 — message` (guardrails-scan)
SCAN_LINE = re.compile(
    r"\[GUARDRAILS\]\[(?P<sev>\w+)\]\s+(?P<rule>\S+)\s+(?P<file>[^\s:]+):(?P<line>\d+)\s+—\s+(?P<msg>.+)"
)


def slug(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].rstrip("-")


def registry_findings(root: Path, explicit: Path | None = None) -> list[dict]:
    # explicit -> single source; otherwise bundled baseline + project overlay.
    entries, _owner = gate_overlay.resolve_registry(root, explicit)
    out = []
    for e in entries:
        fid = e.get("failure_id", "")
        if not fid:
            continue
        out.append({
            "origin": "registry",
            "source_id": fid,
            "category": (e.get("category") or "general").lower(),
            "severity": (e.get("severity") or "medium").lower(),
            "title": (e.get("error_message") or fid)[:120],
            "root_cause": e.get("root_cause", ""),
            "prevention": e.get("prevention_rule", ""),
            "status": e.get("status", "active"),
            "files": e.get("affected_files") or [],
        })
    return out


def scan_findings(stdin_text: str) -> list[dict]:
    """Live scanner violations -> findings. Deduped by (rule, file) so a rule
    firing on ten lines of one file yields one requirement, not ten."""
    seen: dict[tuple[str, str], dict] = {}
    for m in SCAN_LINE.finditer(stdin_text):
        key = (m["rule"], m["file"])
        if key in seen:
            seen[key]["lines"].append(m["line"])
            continue
        stem = m["file"].rsplit("/", 1)[-1].rsplit(".", 1)[0]
        seen[key] = {
            "origin": "scan",
            "source_id": m["rule"],
            "category": slug(stem) or "scan",
            "severity": m["sev"],
            "title": m["msg"].strip(),
            "root_cause": "",
            "prevention": "",
            "status": "active",
            "files": [m["file"]],
            "lines": [m["line"]],
        }
    return list(seen.values())


def render_requirement(f: dict, req_id: str) -> str:
    shall = f["title"].rstrip(".")
    if not shall.lower().startswith("the "):
        shall = f"The system shall prevent: {shall}"
    body = [
        f"### Requirement: {f['title'][:80]}",
        f"<!-- id: {req_id} -->",
        f"{shall}.",
        f"_(origin: {f['origin']} `{f['source_id']}`, severity {f['severity']}, status {f['status']})_",
    ]
    if f["root_cause"]:
        body.append(f"Root cause: {f['root_cause']}")
    if f["prevention"]:
        body.append(f"Prevention rule: {f['prevention']}")
    if f["files"]:
        suffix = ""
        if f.get("lines"):
            suffix = " (current hits: " + ", ".join(f"L{ln}" for ln in f["lines"]) + ")"
        body.append("Affected code: " + ", ".join(f"`{p}`" for p in f["files"]) + suffix)
    body += [
        "",
        "#### Scenario: regression attempt",
        "- **WHEN** the pattern behind this requirement is reintroduced",
        "- **THEN** the guardrails/registry gate fails the commit",
        "",
        f"> Implement, then mark the enforcing source with `// spec: {req_id}`",
        "> so spec_traceability.py counts it covered.",
        "",
    ]
    return "\n".join(body) + "\n"


ORIGIN_LINE = re.compile(r"_\(origin: (\w+) `([^`]+)`,")


def existing_state(spec_path: Path) -> tuple[set[str], set[tuple[str, str]]]:
    """(ids, covered_findings) already present in the spec file.

    Findings are matched by their provenance line, not just by id: the id is
    derived from the finding, but two different findings can slug to the same
    base id (the counter then disambiguates), so "was THIS finding already
    scaffolded?" must key on (origin, source_id).
    """
    if not spec_path.exists():
        return set(), set()
    text = spec_path.read_text()
    ids = set(re.findall(r"<!--\s*id:\s*([a-z0-9-]+)\s*-->", text))
    covered = {(m[0], m[1]) for m in ORIGIN_LINE.findall(text)}
    return ids, covered


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                    help="project root (default: parent of the .devgate submodule)")
    ap.add_argument("--capability", default=None,
                    help="openspec/specs/<capability>/ — grouping dir (default: per-finding category)")
    ap.add_argument("--stdin", action="store_true",
                    help="also fold live guardrails-scan violations (piped on stdin) into findings")
    ap.add_argument("--registry", type=Path, default=None,
                    help="single-source failure registry (default: bundled + overlay merged)")
    ap.add_argument("--list", action="store_true", help="report what would be written; change nothing")
    args = ap.parse_args()

    root = args.root.resolve()
    findings = registry_findings(root, args.registry)
    if args.stdin:
        findings += scan_findings(sys.stdin.read())
    if not findings:
        print("findings-to-spec: no findings from merged registry"
              + (" or stdin" if args.stdin else "") + " — nothing to scaffold.")
        return 0

    by_cap: dict[str, list[dict]] = {}
    for f in findings:
        cap = args.capability or f["category"] or "general"
        by_cap.setdefault(cap, []).append(f)

    # A noisy scanner stream can repeat the same rule; one requirement per
    # (origin, source_id). The registry path is already deduped by merge_by_id.
    for cap in by_cap:
        by_cap[cap] = list({(f["origin"], f["source_id"]): f for f in by_cap[cap]}.values())

    total_new = 0
    for cap, fs in sorted(by_cap.items()):
        spec_dir = root / "openspec" / "specs" / cap
        spec_path = spec_dir / "spec.md"
        have_ids, covered = existing_state(spec_path)
        # Stable ordering: registry-backed first, then scan; by source id.
        fs.sort(key=lambda f: (f["origin"] != "registry", f["source_id"]))
        new_blocks = []
        for f in fs:
            if (f["origin"], f["source_id"]) in covered:
                continue  # this exact finding is already a requirement
            base = slug(f["source_id"])
            req_id = f"{slug(cap, 20)}-{base}"
            n = 2
            while req_id in have_ids:
                req_id = f"{slug(cap, 20)}-{base}-{n}"
                n += 1
            have_ids.add(req_id)
            covered.add((f["origin"], f["source_id"]))
            new_blocks.append(render_requirement(f, req_id))
        if not new_blocks:
            continue
        total_new += len(new_blocks)
        if args.list:
            print(f"would append {len(new_blocks)} requirement(s) to {spec_dir.relative_to(root)}/spec.md")
            continue
        spec_dir.mkdir(parents=True, exist_ok=True)
        header = "" if spec_path.exists() else (
            f"# {cap.replace('-', ' ').title()}\n\n"
            "Status: Proposed. Auto-seeded from gate findings by findings_to_spec.py;\n"
            "edit freely — re-runs only append findings that have no requirement yet.\n\n"
            "## Requirements\n\n"
        )
        with open(spec_path, "a", encoding="utf-8") as fh:
            fh.write(header + "\n".join(new_blocks))
        rel = spec_path.relative_to(root)
        print(f"findings-to-spec: {len(new_blocks)} requirement(s) -> {rel}")

    if total_new:
        print(f"Next: implement each fix, add `// spec: <id>` to the enforcing source, "
              f"and update status via log_failure.py. Check coverage with spec_traceability.py --report.")
    else:
        print("findings-to-spec: every finding already has a requirement — specs are in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
