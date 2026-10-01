#!/usr/bin/env python3
"""Shared openspec coverage discovery — the single implementation the
traceability gate and the gap scanner both import (SGA-05: the two gates
must never report different coverage numbers for the same tree).

Discovers requirement IDs across both standard OpenSpec layouts:
  openspec/specs/<capability>/spec.md          (published specs)
  openspec/changes/<change>/specs/**/*.md      (change packages, archive/ skipped)
and the source markers that cover them (`// spec:` / `# spec:` comment lines).

DRAFT EXCLUSION (SGA-02): a requirement block whose text carries a
`<!-- draft: unreviewed -->` marker is excluded from discovery entirely —
generated drafts cannot inflate the coverage numbers that judge them.
`find_spec_files`/raw text readers still see the file; only the ID map is
filtered. Reviewing a draft means deleting the marker, which admits it.
"""
# spec: sga-05
import re
from pathlib import Path

REQ_ID = re.compile(r"<!--\s*id:\s*([a-z0-9-]+)\s*-->")
DRAFT = re.compile(r"<!--\s*draft:\s*unreviewed\s*-->")
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
# `.gd` joined the set for the gap-scanner work (SGA-07 acceptance 4): game
# repos mark coverage in GDScript source, and a marker the discovery cannot
# read is an uncovered requirement forever. No .gd file exists in this repo
# and MergeKingdom has no markers yet, so no existing number shifts.
SCAN_EXTS = {".rs", ".py", ".mjs", ".js", ".ts", ".sh", ".zig", ".gd"}
SCAN_SKIP = {"target", "node_modules", ".git", "openspec", ".devgate"}


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


def _capability_of(spec: Path) -> str:
    # specs/<cap>/spec.md -> capability dir; flat change specs/<file>.md
    # -> file stem (DevGate's own change packages use that flat layout).
    return spec.parent.name if spec.name == "spec.md" else spec.stem


def _requirement_blocks(text: str) -> list[tuple[str, str]]:
    """(id, block_text) per REQ_ID marker; a block runs to the next marker."""
    marks = list(REQ_ID.finditer(text))
    return [(m.group(1), text[m.start():marks[i + 1].start() if i + 1 < len(marks) else len(text)])
            for i, m in enumerate(marks)]


def collect_requirements(root: Path) -> dict:
    """capability -> {req_id: spec_path}, across both OpenSpec layouts.

    Requirements whose block carries `<!-- draft: unreviewed -->` are not
    counted (SGA-02). Returns the same shape spec_traceability has always
    produced for non-draft trees.
    """
    out = {}
    drafts = 0
    for spec in find_spec_files(root):
        capability = _capability_of(spec)
        ids = _requirement_blocks(spec.read_text(encoding="utf-8"))
        out.setdefault(capability, {})
        for rid, block in ids:
            if DRAFT.search(block):
                drafts += 1
                continue
            out[capability][rid] = spec
    collect_requirements.draft_count = drafts
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
