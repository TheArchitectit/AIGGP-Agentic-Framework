#!/usr/bin/env python3
# spec: fw-corruption-01
"""corruption_diff.py — hunk-accurate diff parsing for the corruption gate.

Split out of scripts/check_corruption.py to keep both under DevGate's own
500-line hard limit (check_corruption.py stood at 518). One file, one concern:
turning a unified diff into hunks of (kind, lineno, text) records, plus the
aligned replacement pairing the substitution-flip judgement needs.

check_corruption.py re-exports the helpers below, so callers and tests keep
importing one module.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

# Gitlink metadata in a unified diff: a commit pointer, not a text file
# (measured flip false positive - see the gitlink test in test_check_corruption).
_GITLINK_META = re.compile(
    r"^(?:index \S+\.\.\S+|new file mode|deleted file mode) 160000$")


def _diff_hunks(diff: str):
    """Yield ``(path, [(kind, lineno, text), ...])`` once per hunk.

    The single diff parser in this gate. ``kind`` is ``+``, ``-`` or a space
    (context). Header lines are recognised ONLY before the first hunk of a
    file, so a removed line whose content begins with ``--`` (``--- a note``
    in Markdown) is data, not a file header.

    Hunks stay separate because the flip judgement is about a place in a file,
    not about a file: see ``_replacement_blocks``.
    """
    path = None
    old_path = None
    hunk: list[tuple[str, int, str]] = []
    old_no = new_no = 0
    seen_plus = False
    gitlink = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            if hunk and path is not None and not gitlink:
                yield path, hunk
            hunk = []
            path = old_path = None
            seen_plus = False
            gitlink = False
            continue
        if not seen_plus and not line.startswith("@@"):
            if _GITLINK_META.match(line):
                gitlink = True         # commit pointer, not text: skip hunks
            elif line.startswith("--- "):
                p = line[4:].strip()
                old_path = p[2:] if p.startswith("a/") else p
            elif line.startswith("+++ "):
                p = line[4:].strip()
                newp = p[2:] if p.startswith("b/") else p
                path = old_path if newp == "/dev/null" else newp
                seen_plus = True
            continue                    # index/new-file-mode/binary metadata
        seen_plus = True
        if line.startswith("@@"):
            if hunk and path is not None and not gitlink:
                yield path, hunk
            hunk = []
            m = re.search(r"-(\d+)(?:,\d+)? \+(\d+)", line)
            old_no = int(m.group(1)) if m else 0
            new_no = int(m.group(2)) if m else 0
        elif line.startswith("\\"):
            continue                    # "\ No newline at end of file"
        elif line.startswith("+"):
            hunk.append(("+", new_no, line[1:]))
            new_no += 1
        elif line.startswith("-"):
            hunk.append(("-", old_no, line[1:]))
            old_no += 1
        else:
            hunk.append((" ", new_no, line[1:]))
            old_no += 1
            new_no += 1
    if hunk and path is not None and not gitlink:
        yield path, hunk


def _gitlink_update_count(diff: str) -> int:
    """Submodule pointer updates in the diff (gitlink blocks, mode 160000)."""
    return sum(any(_GITLINK_META.match(ln) for ln in b.splitlines())
               for b in diff.split("diff --git ")[1:])


def _added_lines(diff: str):
    """Yield (path, new_lineno, text) for added lines, hunk-accurate."""
    for path, hunk in _diff_hunks(diff):
        for kind, lineno, text in hunk:
            if kind == "+":
                yield path, lineno, text


def _removed_lines(diff: str):
    """Yield (path, old_lineno, text) for removed lines, hunk-accurate."""
    for path, hunk in _diff_hunks(diff):
        for kind, lineno, text in hunk:
            if kind == "-":
                yield path, lineno, text


def _replacement_blocks(hunk):
    """Yield ``(removed_lines, added_lines)`` for each ALIGNED replacement.

    A substitution flip can only exist where a line was actually replaced by a
    line. Two things are therefore required before two lines may be compared:

    1. They must sit in the same hunk. A pure insertion replaces nothing, so
       pairing it against lines a later hunk removed invents replacements
       (measured: a 15-line comment block above one edited line produced three
       false findings at scripts/check_charset.py:149,151,152).
    2. They must be ALIGNED to each other. Within one change block git emits
       every removal then every addition, so a rewritten function is a single
       run of N removals and M additions; pairing those by index drifts as
       soon as N != M and compares unrelated lines (measured on
       scripts/check_corruption.py itself: ``elif line.startswith("@@@"):``
       was paired with ``path = old_path = None``).

    The alignment is a line-level SequenceMatcher over the hunk's two sides.
    Only a ``replace`` opcode whose sides have EQUAL length is paired, because
    a character substitution replaces k lines with k lines in place. A
    same-length pair is compared index-wise inside that block and nowhere
    else.

    Named limit: an in-place substitution buried inside a block whose line
    counts differ is NOT compared, and so is not reported. That is a deliberate
    false-negative for the false-positive this gate shipped; whole-file
    rewrites remain covered by the mass-rewrite rule in scan_diff. The caller
    also skips flip pairing for whole-file rewrites outright (scan_diff): a
    rewrite asserts no line correspondence at all, so its equal-size
    alignment blocks pair unrelated lines (measured 2026-10-27 on the
    invites.ts barrel split — a deleted 'This replaces the Phase-1
    FIXTURE_INVITES map…' comment paired with an added 'Every public name
    this module historically exported…' comment: 78% "changed", length
    within 3%, called a substitution flip). Those files are judged by the
    mass-rewrite rule alone.
    """
    rems = [text for kind, _ln, text in hunk if kind == "-"]
    adds = [(ln, text) for kind, ln, text in hunk if kind == "+"]
    if not rems or not adds:
        return
    matcher = SequenceMatcher(None, rems, [text for _ln, text in adds],
                              autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "replace":
            continue
        if (i2 - i1) != (j2 - j1):
            continue        # unequal sizes: no correspondence to assert
        yield rems[i1:i2], adds[j1:j2]
