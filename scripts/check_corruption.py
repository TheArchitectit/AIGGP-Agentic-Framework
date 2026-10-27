#!/usr/bin/env python3
# spec: fw-corruption-01
"""check_corruption.py — data-corruption gate (fw-corruption-01).

fw-charset-01 governs which characters may appear; fw-encoding-01 governs a
file's encoding and line endings. This gate governs *corruption*: bytes or
characters that were once valid and are now damaged, plus the mass-mutation
shape that ransomware and bad bulk edits produce.

Two modes:

**Content scan (default).** Every tracked text file is inspected for:
  * U+FFFD REPLACEMENT CHARACTER — the tell-tale of a lossy decode;
  * mojibake — UTF-8 bytes re-decoded as Latin-1 ("\u00c2\u00a7", "\u00e2\u20ac\u2122",
    "\u00c3\u00a9"); the C1 control block (U+0080-U+009F) is a near-certain signal;
  * C0/C1 control characters that are not tab/newline/CR;
  * zero-width and bidi-override characters (invisible, can reorder text);
  * NUL bytes inside a text file.

**Diff scan (`--range A..B`, or `--staged`).** Detects a *bad data flip*: a
change that substitutes characters in place rather than editing meaning. A
changed line whose length is within +/-15% of the original and whose
character-level difference exceeds 60% is a substitution flip. A file where
most lines changed at once is reported as a mass rewrite (the ransomware /
runaway-script shape) and FAILS unless it is on the reviewed allowlist.
Submodule pointer updates (gitlink, mode 160000) are skipped: a pin bump
is a commit pointer, not text. A pin-bump-only diff passes with a note.

Fail-closed, non-vacuous: a zero-file scan FAILS; a zero-line diff scan
FAILS; the ratchet baseline may only decrease.

The hunk-level diff parser the diff scan is built on (_diff_hunks and the
replacement pairing) lives in scripts/corruption_diff.py — split out to keep
both modules under DevGate's own 500-line hard limit (this file stood at 518).
It is re-exported below so callers and tests keep importing one module.

Exit: 0 clean; 1 violations; 2 usage.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

# Sibling-module bootstrap (the regression_diff.py idiom): make the split-out
# diff parser importable both when run as a script (its dir is sys.path[0]) and
# when loaded via importlib by the tests (dir NOT on sys.path).
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

EXIT_OK = 0
EXIT_VIOLATIONS = 1
EXIT_USAGE = 2

BASELINE = Path(".guardrails") / "corruption-baseline.json"
ALLOWLIST = Path(".guardrails") / "corruption-allowlist.json"

REPLACEMENT = "\ufffd"
# C1 controls are almost always mojibake (UTF-8 continuation bytes 0x80-0xBF
# decoded as Latin-1). C0 controls other than tab/LF/CR are never intended.
C1 = re.compile(r"[\u0080-\u009f]")
C0 = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]")
ZW_BIDI = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff]")
MOJIBAKE = re.compile(
    r"\u00c2[\u00a0-\u00bf]"          # A-circumflex + latin-1 (section sign etc)
    r"|\u00e2\u20ac[\u0080-\u00ff]?"  # a-circumflex + euro (curly quotes)
    r"|\u00c3[\u0080-\u00bf]"         # A-tilde + high byte (e-acute, e-grave)
    r"|\u00ef\u00bb\u00bf"            # BOM mis-read as Latin-1
)

FLIP_LEN_TOLERANCE = 0.15
FLIP_DIFF_RATIO = 0.60
MASS_REWRITE_RATIO = 0.60
MASS_REWRITE_MIN_LINES = 8
# A single commit that rewrites this many whole files is the bulk-mutation
# (ransomware / runaway-script) shape, not an edit.
BULK_MUTATION_FILES = 10


def _load_gate_common():
    here = Path(__file__).resolve()
    for cand in (here.parent, here.parent.parent / "scripts"):
        if (cand / "gate_common.py").is_file():
            sys.path.insert(0, str(cand))
            break
    import gate_common  # noqa: E402
    return gate_common


def tracked_files(root: Path) -> list[str]:
    r = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        print(f"check-corruption: FAIL - git ls-files failed: {r.stderr}",
              file=sys.stderr)
        sys.exit(EXIT_USAGE)
    return [f for f in r.stdout.split("\0") if f]


def load_json_map(root: Path, name: Path, kind: str) -> dict:
    path = root / name
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"check-corruption: FAIL - {kind} unreadable: {exc}", file=sys.stderr)
        sys.exit(EXIT_USAGE)
    return data


def load_baseline(root: Path) -> dict[str, int]:
    data = load_json_map(root, BASELINE, "baseline")
    files = data.get("files") or {}
    if not isinstance(files, dict):
        print("check-corruption: FAIL - baseline 'files' must be an object",
              file=sys.stderr)
        sys.exit(EXIT_USAGE)
    return {k: int(v) for k, v in files.items()}


def load_allowlist(root: Path) -> dict[str, str]:
    data = load_json_map(root, ALLOWLIST, "allowlist")
    entries = data.get("entries") or []
    out: dict[str, str] = {}
    for row in entries:
        if not isinstance(row, dict) or not str(row.get("reason", "")).strip():
            print(f"check-corruption: FAIL - allowlist row without a reason: {row!r}",
                  file=sys.stderr)
            sys.exit(EXIT_USAGE)
        p = row.get("path")
        if not p:
            print(f"check-corruption: FAIL - allowlist row without a path: {row!r}",
                  file=sys.stderr)
            sys.exit(EXIT_USAGE)
        out[p] = row["reason"]
    return out


def content_findings(text: str) -> list[str]:
    out: list[str] = []
    if REPLACEMENT in text:
        out.append(f"U+FFFD replacement char x{text.count(REPLACEMENT)} "
                   f"(lossy decode)")
    m = MOJIBAKE.findall(text)
    if m:
        out.append(f"mojibake sequence x{len(m)} (UTF-8 re-decoded as Latin-1)")
    c1 = C1.findall(text)
    if c1:
        out.append(f"C1 control char x{len(c1)} (near-certain mojibake)")
    c0 = C0.findall(text)
    if c0:
        out.append(f"C0 control char x{len(c0)}")
    zw = ZW_BIDI.findall(text)
    if zw:
        out.append(f"zero-width/bidi char x{len(zw)} (invisible)")
    if "\x00" in text:
        out.append(f"NUL byte x{text.count(chr(0))} in a text file")
    return out


def scan_content(root: Path, gc, skip_dirs, allow: dict[str, str],
                 baseline: dict[str, int], max_report: int) -> int:
    files = [f for f in tracked_files(root) if gc.is_text_file(f)]
    files = [f for f in files
             if not any(p in skip_dirs for p in Path(f).parts)]
    per_file: dict[str, list[str]] = {}
    scanned = 0
    for rel in files:
        try:
            data = (root / rel).read_bytes()
        except OSError:
            continue
        scanned += 1
        if rel in allow:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            per_file[rel] = [f"not valid UTF-8 at byte {exc.start}"]
            continue
        found = content_findings(text)
        if found:
            per_file[rel] = found
    if scanned == 0:
        print("check-corruption: FAIL - zero text files scanned (no vacuous green)",
              file=sys.stderr)
        return EXIT_VIOLATIONS
    over = {k: v for k, v in per_file.items() if len(v) > baseline.get(k, 0)}
    improved = {k for k in baseline
                if len(per_file.get(k, [])) < baseline[k]}
    if over:
        total = sum(len(v) for v in over.values())
        print(f"check-corruption: FAIL - {len(over)} file(s) exceed their "
              f"corruption baseline (fw-corruption-01); {total} finding(s)")
        shown = 0
        for rel in sorted(over):
            for f in over[rel]:
                if shown >= max_report:
                    break
                print(f"  {rel}: {f}")
                shown += 1
        if shown < total:
            print(f"  ... and {total - shown} more")
        print("  fix: restore the file from git history and re-encode it "
              "(lossy decode is not reversible); if the bytes are a deliberate "
              "fixture, add a reasoned row to .guardrails/corruption-allowlist.json")
        return EXIT_VIOLATIONS
    if improved:
        print(f"check-corruption: note - {len(improved)} file(s) improved below "
              f"baseline; tighten .guardrails/corruption-baseline.json")
    grand = sum(baseline.get(k, 0) for k in per_file)
    print(f"check-corruption: OK - {scanned} text file(s) within baseline "
          f"({grand} grandfathered finding(s))")
    return EXIT_OK


# The hunk-level diff parser (_GITLINK_META, _diff_hunks and the hunk/line
# helpers built on it) moved to scripts/corruption_diff.py (500-line cap
# split); re-exported here so callers and tests keep importing one module.
from corruption_diff import (  # noqa: E402
    _GITLINK_META, _added_lines, _diff_hunks, _gitlink_update_count,
    _removed_lines, _replacement_blocks)


def scan_diff(diff: str, allow: dict[str, str], max_report: int,
              strict_mass_rewrite: bool = False) -> int:
    added = list(_added_lines(diff))
    removed = list(_removed_lines(diff))
    if not added and not removed:
        # Pin bumps only is a real range with nothing textual to judge; zero
        # lines with zero pin bumps means an empty range - vacuous, so FAILS.
        gitlinks = _gitlink_update_count(diff)
        if gitlinks:
            print(f"check-corruption: OK - diff scan: {gitlinks} submodule "
                  f"pointer update(s) (gitlink) - nothing textual to judge")
            return EXIT_OK
        print("check-corruption: FAIL - diff scan evaluated zero lines "
              "(no vacuous green)", file=sys.stderr)
        return EXIT_VIOLATIONS

    fails: list[str] = []
    warnings: list[str] = []

    # Flip detection: pair removed/added lines ONLY inside the contiguous -/+
    # run git reports, in order; a same-length line with a high character-level
    # difference is a substitution flip. A run is scoped to a hunk, because a
    # pure insertion replaces nothing and must not be paired with anything.
    from collections import defaultdict
    rem_by_file: dict[str, int] = defaultdict(int)
    add_by_file: dict[str, int] = defaultdict(int)
    for p, _ln, _t in removed:
        rem_by_file[p] += 1
    for p, _ln, _t in added:
        add_by_file[p] += 1

    # Whole-file rewrites assert no line correspondence (see
    # _replacement_blocks): their equal-size alignment blocks pair unrelated
    # lines and invent substitution flips. They are judged by the mass-rewrite
    # rule below alone (warn by default, fatal under --strict-mass-rewrite,
    # counted toward BULK MUTATION).
    rewrite_paths = {
        p for p in add_by_file
        if add_by_file[p] >= MASS_REWRITE_MIN_LINES
        and rem_by_file[p] >= MASS_REWRITE_MIN_LINES
    }

    for path, hunk in _diff_hunks(diff):
        if path in allow or path in rewrite_paths:
            continue
        for rems, adds in _replacement_blocks(hunk):
            for i in range(min(len(rems), len(adds))):
                ln, new = adds[i]
                old = rems[i]
                if len(old) < 8:
                    continue
                ratio = 1.0 - SequenceMatcher(None, old, new).ratio()
                len_delta = abs(len(new) - len(old)) / max(1, len(old))
                if len_delta <= FLIP_LEN_TOLERANCE and ratio >= FLIP_DIFF_RATIO:
                    fails.append(
                        f"{path}:{ln}: substitution flip "
                        f"({ratio*100:.0f}% of characters changed, "
                        f"length within {len_delta*100:.0f}%)")

    bulk_files = 0
    for path in sorted(add_by_file):
        if path in allow:
            continue
        # A whole-file rewrite: many added AND many removed lines at once.
        if (add_by_file[path] >= MASS_REWRITE_MIN_LINES
                and rem_by_file[path] >= MASS_REWRITE_MIN_LINES):
            bulk_files += 1
            msg = (f"{path}: MASS REWRITE - {add_by_file[path]} added / "
                   f"{rem_by_file[path]} removed line(s) in one change")
            (fails if strict_mass_rewrite else warnings).append(msg)

    if bulk_files >= BULK_MUTATION_FILES:
        fails.append(
            f"BULK MUTATION - {bulk_files} whole files rewritten in one change "
            f"(ransomware / runaway-script shape)")

    if fails:
        print(f"check-corruption: FAIL - {len(fails)} data-flip / "
              f"bulk-mutation finding(s) (fw-corruption-01)")
        for f in fails[:max_report]:
            print(f"  {f}")
        print("  fix: verify the change is intentional; a substitution flip or "
              "bulk mutation is the shape of corruption, not an edit")
        return EXIT_VIOLATIONS

    for w in warnings[:max_report]:
        print(f"check-corruption: WARNING - {w}")
    skipped = _gitlink_update_count(diff)
    print(f"check-corruption: OK - diff scan clean "
          f"({len(added)} added / {len(removed)} removed line(s), "
          f"{bulk_files} whole-file rewrite(s) warned"
          + (f", {skipped} gitlink pin update(s) skipped" if skipped else "")
          + ")")
    return EXIT_OK


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="check_corruption",
        description="data-corruption + bad-flip gate (fw-corruption-01)")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--range", help="git revision range A..B (diff scan)")
    ap.add_argument("--staged", action="store_true", help="scan the staged diff")
    ap.add_argument("--no-baseline", action="store_true")
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--strict-mass-rewrite", action="store_true",
                    help="treat a single whole-file rewrite as fatal (default: warn)")
    args = ap.parse_args()

    root = Path(args.repo).resolve()
    gc = _load_gate_common()
    try:
        skip_dirs = gc.load_skip_dirs()
    except Exception as exc:
        print(f"check-corruption: FAIL - cannot load scope contract: {exc}",
              file=sys.stderr)
        return EXIT_USAGE

    allow = load_allowlist(root)
    max_report = 10**9 if args.list else 30

    if args.range or args.staged:
        cmd = ["git", "-C", str(root), "diff", "--no-color", "--unified=0"]
        if args.range:
            cmd.append(args.range)
        else:
            cmd.append("--cached")
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print(f"check-corruption: FAIL - git diff failed: {r.stderr}",
                  file=sys.stderr)
            return EXIT_USAGE
        return scan_diff(r.stdout, allow, max_report, args.strict_mass_rewrite)

    if args.write_baseline:
        files = [f for f in tracked_files(root) if gc.is_text_file(f)]
        files = [f for f in files
                 if not any(p in skip_dirs for p in Path(f).parts)]
        per: dict[str, int] = {}
        for rel in files:
            if rel in allow:
                continue
            try:
                text = (root / rel).read_bytes().decode("utf-8")
            except (OSError, UnicodeDecodeError):
                per[rel] = per.get(rel, 0) + 1
                continue
            n = len(content_findings(text))
            if n:
                per[rel] = n
        doc = {"api_version": "devgate.corruption-baseline/v1",
               "note": ["fw-corruption-01 ratchet: grandfathered corruption.",
                        "May only DECREASE."],
               "files": dict(sorted(per.items()))}
        (root / BASELINE).write_text(json.dumps(doc, indent=1) + "\n",
                                     encoding="utf-8")
        print(f"check-corruption: wrote baseline - {len(per)} file(s), "
              f"{sum(per.values())} finding(s)")
        return EXIT_OK

    baseline = {} if args.no_baseline else load_baseline(root)
    return scan_content(root, gc, skip_dirs, allow, baseline, max_report)


if __name__ == "__main__":
    sys.exit(main())
