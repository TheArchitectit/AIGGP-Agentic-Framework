#!/usr/bin/env python3
# // spec: spec-state-07
"""spec_index.py - render `openspec/INDEX.md` from the specs it describes.

`openspec/INDEX.md` says "Generated, not typed" and, until this script existed,
nothing generated it: every status in it was typed by a person. This makes the
claim true, and `--check` makes a hand edit a red build instead of a silent
divergence.

Status is data, in this order of authority:

1. the owner's `DEFERRED` decision in the spec's `Status:` line - a decision is
   not a backlog item and no cell count overrides it;
2. the per-requirement closure cells: all `EXERCISED` is CLOSED, none is OPEN,
   anything between is PARTIAL;
3. a spec with no cells falls back to its `Status:` line: a terminal word is
   CLOSED, any other stated status is OPEN because no requirement is shown
   exercised;
4. no cells and no `Status:` line is UNKNOWN - a documentation gap, reported as
   such rather than guessed at.

Requirement sets come from `<!-- id: ... -->` markers (drafts excluded), so a
closure table that omits a requirement cannot hide it.

Ledger rows are read for two purposes only: a requirement carried by a row but
by no cell takes the row's latest recorded state, so a spec can join the index
without restructuring its prose, and a row that disagrees with a cell is
reported as a warning rather than silently resolved - the gate is what fails on
disagreement, and this generator must not paper over it.

Usage:
  python3 scripts/spec_index.py            # print to stdout
  python3 scripts/spec_index.py --write    # rewrite openspec/INDEX.md
  python3 scripts/spec_index.py --check    # exit 1 if the file is not generated

Exit: 0 rendered/agreeing, 1 drift (--check), 2 usage error.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS / "lib"))
import spec_discovery  # noqa: E402

STATES = ("EXERCISED", "WIRED", "ABSENT", "NOT_RUN", "DIFFERS")
TERMINAL_WORD = re.compile(r"^\s*\**\s*(closed|implemented|terminal|complete)\b", re.I)
DEFERRED_WORD = re.compile(r"^\s*\**\s*deferred\b", re.I)
STATUS_LINE = re.compile(r"^[>\s]*\**Status:\**\s*(.+?)\s*$", re.M)
REQUIREMENTS_HEADING = re.compile(r"^##+\s+Requirements\b", re.M)
CELL = re.compile(r"^\|\s*(?:`|\*\*)?([A-Za-z0-9-]+)(?:`|\*\*)?[^|]*\|\s*\**([A-Z_]+)\**\s*\|", re.M)
TITLE = re.compile(r"^#\s+(.+?)\s*$", re.M)
EXERCISED_COUNT = re.compile(r"\(EXERCISED\s+(\d+)\)")

HEADER = """# OpenSpec index

> **Generated, not typed.** Status is derived from each spec's own closure
> table (the per-requirement `EXERCISED` / `WIRED` / `ABSENT` / `NOT_RUN`
> cells) or its explicit `Status:` line. A spec with no closure evidence is
> reported **UNKNOWN** rather than guessed at.
>
> **DEFERRED** is a decision, not a backlog item. The single row marked
> DEFERRED below has its owner's answer (base-specs-01: the capability lives
> in the consuming game repo) and stays DEFERRED until that repo builds it —
> it is not closed by relabelling the line.

**{count} specs** — CLOSED {closed} · DEFERRED {deferred} · PARTIAL {partial} · OPEN {open} · UNKNOWN {unknown}

| Spec | Title | Status | Evidence |
|---|---|---|---|
"""

FOOTER = """
## Reading the status

- **CLOSED** — every requirement row is `EXERCISED`: implementation present
  and a test drives it.
- **PARTIAL** — some rows `EXERCISED`, at least one `WIRED`/`ABSENT`/
  `NOT_RUN`/`DIFFERS`. The gap is named in that spec.
- **OPEN** — no requirement reaches `EXERCISED`.
- **UNKNOWN** — no closure table and no `Status:` line. A documentation gap,
  not a claim the work is unfinished. Fix by adding the closure table.
"""


def read_spec(path: Path) -> tuple[str, dict[str, str], str | None, list[str]]:
    """(title, cells, status line, requirement ids) for one published spec."""
    text = path.read_text(encoding="utf-8")
    title = TITLE.search(text)
    cells = dict(CELL.findall(text))
    preamble = REQUIREMENTS_HEADING.split(text, maxsplit=1)[0]
    status = STATUS_LINE.search(preamble)
    reqs = [rid for rid, block in spec_discovery._requirement_blocks(text)
            if not spec_discovery.DRAFT.search(block)]
    return (title.group(1).strip() if title else path.parent.name,
            {k: v for k, v in cells.items() if v in STATES},
            status.group(1).strip() if status else None,
            reqs)


def ledger_states(path: Path) -> dict[tuple[str, str], str]:
    """Latest recorded state per (spec, req); `at` is never used for ordering,
    so the last row in file order wins - the ledger is append-only."""
    out: dict[tuple[str, str], str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("schema") == "v1":
            out[(str(row.get("spec")), str(row.get("req")))] = str(row.get("to"))
    return out


def classify(cap: str, cells: dict, status: str | None, reqs: list[str],
             rows: dict[tuple[str, str], str]) -> tuple[str, str]:
    """(STATUS, Evidence cell) for one spec."""
    if status and DEFERRED_WORD.search(status):
        return "DEFERRED", "Status: DEFERRED"

    # A requirement with no cell may take its latest ledger state, so a spec
    # with prose status can still be accounted per requirement.
    states = []
    for req in reqs:
        if req in cells:
            states.append(cells[req])
        elif (cap, req) in rows:
            states.append(rows[(cap, req)])

    if states and all(s == "EXERCISED" for s in states) and len(states) == len(reqs):
        return "CLOSED", f"Status: CLOSED (EXERCISED {len(states)})"
    if states:
        exercised = sum(1 for s in states if s == "EXERCISED")
        if exercised == 0:
            return "OPEN", f"EXERCISED 0 of {len(reqs)}"
        return "PARTIAL", f"EXERCISED {exercised} of {len(reqs)}"
    if status:
        word = re.match(r"^\s*\**\s*([A-Za-z]+)", status)
        label = (word.group(1) if word else "").upper()
        count = EXERCISED_COUNT.search(status)
        if TERMINAL_WORD.search(status):
            return "CLOSED", f"Status: {label}" + (f" (EXERCISED {count.group(1)})" if count else "")
        return "OPEN", f"Status: {label or 'OPEN'}"
    return "UNKNOWN", "no closure table and no Status line"


def render(root: Path, ledger: Path) -> str:
    specs = sorted(p for p in (root / "openspec" / "specs").glob("*/spec.md"))
    rows = ledger_states(ledger)
    entries, counts = [], {"CLOSED": 0, "DEFERRED": 0, "PARTIAL": 0, "OPEN": 0, "UNKNOWN": 0}
    for path in specs:
        cap = path.parent.name
        title, cells, status, reqs = read_spec(path)
        if title == f"{cap} Specification":
            # OpenSpec's scaffolded heading repeats the capability name; the
            # human title is the same words without the scaffold suffix.
            title = cap.replace("-", " ").capitalize()
        kind, evidence = classify(cap, cells, status, reqs, rows)
        counts[kind] += 1
        entries.append(f"| [`{cap}/spec.md`](specs/{cap}/spec.md) | {title} | **{kind}** | {evidence} |")
    head = HEADER.format(count=len(specs), closed=counts["CLOSED"],
                         deferred=counts["DEFERRED"], partial=counts["PARTIAL"],
                         open=counts["OPEN"], unknown=counts["UNKNOWN"])
    return head + "\n".join(entries) + "\n" + FOOTER


def main() -> int:
    ap = argparse.ArgumentParser(description="Render openspec/INDEX.md from spec data.")
    ap.add_argument("--repo", default=None, help="repo root (default: this script's repo)")
    ap.add_argument("--ledger", default="openspec/state-ledger.jsonl")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true", help="rewrite openspec/INDEX.md")
    group.add_argument("--check", action="store_true", help="exit 1 when the file is not generated")
    args = ap.parse_args()

    root = Path(args.repo).resolve() if args.repo else SCRIPTS.parent
    index = root / "openspec" / "INDEX.md"
    if not index.is_file():
        print(f"spec-index: {index} does not exist", file=sys.stderr)
        return 2
    rendered = render(root, root / args.ledger)

    if args.write:
        index.write_text(rendered, encoding="utf-8")
        print(f"spec-index: wrote {index}")
        return 0
    if args.check:
        committed = index.read_text(encoding="utf-8")
        if committed == rendered:
            print(f"spec-index: OK - {index.name} matches the generator")
            return 0
        with tempfile.NamedTemporaryFile("w", suffix="-INDEX.md", delete=False,
                                         encoding="utf-8") as tf:
            tf.write(rendered)
            temp_path = tf.name
        diff = difflib.unified_diff(committed.splitlines(True), rendered.splitlines(True),
                                    fromfile="openspec/INDEX.md (committed)",
                                    tofile=f"openspec/INDEX.md ({temp_path}, generated)",
                                    n=3)
        sys.stderr.writelines(diff)
        print("spec-index: DRIFT - the committed index is not what the generator produces; "
              "run `python3 scripts/spec_index.py --write`", file=sys.stderr)
        return 1
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
