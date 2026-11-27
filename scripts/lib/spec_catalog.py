"""Deterministic capability and change catalog for the generated OpenSpec index."""
# spec: spec-state-07
from __future__ import annotations

import re
from pathlib import Path

import spec_discovery

REQUIREMENT_HEADING = re.compile(r"^### Requirement:\s*(.+?)\s*$", re.M)
TITLE = re.compile(r"^#\s+(.+?)\s*$", re.M)
GENERIC_TITLES = {"proposal", "change"}


def _slug(text: str) -> str:
    # Match github-slugger: retain existing hyphens (including repeated ones),
    # remove punctuation, and replace each rendered whitespace with a hyphen.
    text = text.lower().strip()
    punctuation = set("\\'!\"#$%&()*+,./:;<=>?@[\\]^`{|}~")
    return "".join("-" if char.isspace() else char
                   for char in text
                   if char not in punctuation and
                   not ("\u2000" <= char <= "\u206f") and
                   not ("\u2e00" <= char <= "\u2e7f"))


def _requirement_links(spec_path: Path, root: Path, req_ids: list[str]) -> str:
    text = spec_path.read_text(encoding="utf-8")
    parsed_ids = {rid for rid, block in spec_discovery._requirement_blocks(text)
                  if not spec_discovery.DRAFT.search(block)}
    headings = list(REQUIREMENT_HEADING.finditer(text))
    anchors: dict[str, str] = {}
    used: dict[str, int] = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        marker = spec_discovery.REQ_ID.search(text, heading.end(), end)
        if not marker or marker.group(1) not in parsed_ids:
            continue
        rid = marker.group(1)
        base = _slug(f"Requirement: {heading.group(1)}")
        occurrence = used.get(base, 0)
        used[base] = occurrence + 1
        anchors[rid] = base if occurrence == 0 else f"{base}-{occurrence}"
    rel_spec = spec_path.relative_to(root / "openspec").as_posix()
    return ", ".join(
        f"[`{rid}`]({rel_spec}#{anchors[rid]})" if rid in anchors
        else f"[`{rid}`]({rel_spec})"
        for rid in req_ids
    ) or "—"


def _markdown_link(path: Path, root: Path, label: str) -> str:
    rel = path.relative_to(root / "openspec").as_posix()
    if path.is_dir():
        rel += "/"
    return f"[{label}]({rel})"


def _change_artifacts(change: Path, root: Path) -> list[str]:
    links = []
    primary = (("proposal.md", "proposal"), ("tasks.md", "tasks"),
               ("design.md", "design"), ("evidence.md", "evidence"),
               ("review.md", "review"))
    for name, label in primary:
        path = change / name
        if path.is_file():
            links.append(_markdown_link(path, root, label))

    primary_names = {name for name, _label in primary}
    for path in sorted(change.glob("*.md")):
        if path.name not in primary_names:
            links.append(_markdown_link(path, root, path.stem))

    delta_root = change / "specs"
    if delta_root.is_dir():
        for path in sorted(delta_root.rglob("*.md")):
            label = "delta: " + path.relative_to(delta_root).with_suffix("").as_posix()
            links.append(_markdown_link(path, root, label))

    readme = change / "README.md"
    metadata = change / ".openspec.yaml"
    for path, label in ((readme, "README"), (metadata, "OpenSpec metadata")):
        if path.is_file() and not any(link.endswith(f"]({path.relative_to(root / 'openspec').as_posix()})")
                                       for link in links):
            links.append(_markdown_link(path, root, label))

    batch_dirs = list(change.glob("batch-*"))
    batch_root = change / "batches"
    if batch_root.is_dir():
        batch_dirs.extend(batch_root.glob("batch-*"))
    for batch in sorted((p for p in batch_dirs if p.is_dir()), key=lambda p: p.as_posix()):
        entry = next((batch / candidate for candidate in
                      ("README.md", "batch-manifest.json", "batch-disposition.jsonl")
                      if (batch / candidate).is_file()), None)
        if entry is None:
            entry = next(iter(sorted(batch.glob("*-disposition.jsonl"))), None)
        if entry is None:
            entry = next(iter(sorted(batch.glob("*.md"))), None)
        if entry is not None:
            label = f"{batch.parent.name}/{batch.name}" if batch.parent == batch_root else batch.name
            links.append(_markdown_link(entry, root, label))
        else:
            label = f"{batch.parent.name}/{batch.name}" if batch.parent == batch_root else batch.name
            links.append(f"[{label}](changes/{batch.relative_to(root / 'openspec').as_posix()}/)")
    if not links:
        # Even legacy/minimal package directories without a proposal stay
        # navigable from the catalog. Include archive/ in the path when present.
        links.append(_markdown_link(change, root, "directory"))
    return links


def _change_title(change: Path) -> str:
    proposal = change / "proposal.md"
    if proposal.is_file():
        match = TITLE.search(proposal.read_text(encoding="utf-8"))
        if match:
            title = match.group(1).strip()
            if title.lower().removeprefix("change:").strip() not in GENERIC_TITLES:
                return title
    return change.name.replace("-", " ").capitalize()


def render(root: Path, capabilities: list[tuple[str, str, list[str], str]]) -> str:
    """Render all published capabilities and active/archived change packages.

    Each capability tuple is ``(slug, title, requirement_ids, lifecycle)``.
    Change directory presence, rather than proposal presence, defines the
    inventory, so older/minimal packages remain discoverable.
    """
    lines = ["\n## Capability catalog\n",
             "Every published capability and requirement is linked to its canonical specification.\n",
             "| Capability | Requirements | Lifecycle |\n|---|---|---|"]
    for slug, title, req_ids, lifecycle in capabilities:
        req_links = _requirement_links(root / "openspec" / "specs" / slug / "spec.md",
                                       root, req_ids)
        lines.append(f"| [{title}](specs/{slug}/spec.md) (`{slug}`) | {req_links} | **{lifecycle}** |")

    changes_root = root / "openspec" / "changes"
    active = ([p for p in sorted(changes_root.iterdir(), key=lambda p: p.name)
               if p.is_dir() and p.name != "archive"]
              if changes_root.is_dir() else [])
    archive_root = changes_root / "archive"
    archived = ([p for p in sorted(archive_root.iterdir(), key=lambda p: p.name)
                 if p.is_dir()] if archive_root.is_dir() else [])

    for heading, entries in (("Active changes", active), ("Archived changes", archived)):
        lines.extend([f"\n## {heading}\n",
                      f"{len(entries)} {heading.lower()} are cataloged from their change directories.\n",
                      "| Change | Links |\n|---|---|"])
        for path in entries:
            artifacts = _change_artifacts(path, root)
            title = _change_title(path).replace("|", "&#124;").replace("\n", " ")
            lines.append(f"| {title} (`{path.name}`) | {' · '.join(artifacts)} |")

    lines.extend(["\n## Supporting materials\n",
                  "Entry points for project context, standalone records, evidence, audits, and lifecycle data.\n"])
    materials = []
    openspec = root / "openspec"
    for path in sorted(openspec.iterdir(), key=lambda p: p.name):
        if path.is_file() and path.name != "INDEX.md":
            materials.append((path, path.name))
    for dirname in ("audits", "evidence", "aiggp-source"):
        path = openspec / dirname
        if path.is_dir():
            materials.append((path, f"{dirname}/"))
    for path in sorted((openspec / "changes").glob("*.md")):
        materials.append((path, path.name))

    dg02 = openspec / "changes" / "dg-02-evidence-ledger-reconciliation"
    for name in ("unproven-baseline-roster.jsonl", "input-manifest.json",
                 "roster-evidence.md", "task-1.2-evidence.md",
                 "task-1.2-disposition.jsonl"):
        path = dg02 / name
        if path.is_file():
            materials.append((path, f"dg-02/{name}"))
    for path, label in materials:
        lines.append(f"- {_markdown_link(path, root, label)}")
    return "\n".join(lines) + "\n"
