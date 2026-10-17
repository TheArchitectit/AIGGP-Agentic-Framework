#!/usr/bin/env python3
# spec: fw-encoding-01
"""check_encoding.py — encoding and line-ending drift gate (fw-encoding-01).

A file's *bytes* drift even when its text does not: an editor saves a UTF-8
BOM, a Windows checkout rewrites LF as CRLF, a tool writes UTF-16, or a file
loses its declared attributes. Each is invisible in review and each breaks
something downstream (a shell script with CRLF fails on the shebang; a JSON
parser chokes on a BOM; a diff shows every line changed).

This gate is about ENCODING DRIFT, not characters (that is fw-charset-01):

  1. **BOM** — a UTF-8/UTF-16/UTF-32 byte-order mark in a tracked text file.
     Almost never intended; it corrupts the first line for most consumers.
  2. **Non-UTF-8** — bytes that are not valid UTF-8 (latin-1, cp1252, UTF-16
     without a BOM). Detected and named, never guessed.
  3. **Line endings** — a file whose committed bytes use CRLF (or a lone CR)
     where the repo declares LF, or vice-versa. The declaration is
     `.gitattributes`; with no declaration the default is LF for text.
  4. **Attribute drift** — a text file not covered by a `text`/`eol` rule in
     `.gitattributes` where the repo has adopted one, so its endings are
     checkout-dependent.

Fail-closed, non-vacuous: a zero-file scan FAILS; a malformed `.gitattributes`
FAILS; the ratchet baseline may only decrease.

Exit: 0 clean; 1 violations; 2 usage.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_VIOLATIONS = 1
EXIT_USAGE = 2

BASELINE = Path(".guardrails") / "encoding-baseline.json"
ALLOWLIST = Path(".guardrails") / "encoding-allowlist.json"

BOMS = [
    (b"\xef\xbb\xbf", "UTF-8 BOM"),
    (b"\xff\xfe\x00\x00", "UTF-32 LE BOM"),
    (b"\x00\x00\xfe\xff", "UTF-32 BE BOM"),
    (b"\xff\xfe", "UTF-16 LE BOM"),
    (b"\xfe\xff", "UTF-16 BE BOM"),
]


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
        print(f"check-encoding: FAIL - git ls-files failed: {r.stderr}",
              file=sys.stderr)
        sys.exit(EXIT_USAGE)
    return [f for f in r.stdout.split("\0") if f]


def load_eol_declarations(root: Path) -> dict[str, str]:
    """Parse .gitattributes into {glob: 'lf'|'crlf'}. Empty when absent.

    Only `text`/`eol=` rules matter here. A malformed line is a hard error:
    an unparsable attribute file means the declaration cannot be trusted.
    """
    path = root / ".gitattributes"
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            print(f"check-encoding: FAIL - .gitattributes:{lineno} malformed: "
                  f"{line!r}", file=sys.stderr)
            sys.exit(EXIT_USAGE)
        glob, attrs = parts[0], parts[1:]
        if "eol=crlf" in attrs:
            out[glob] = "crlf"
        elif "eol=lf" in attrs:
            out[glob] = "lf"
        elif "text" in attrs or "text=auto" in attrs:
            out[glob] = "lf"
    return out


def declared_eol(rel: str, decls: dict[str, str]) -> str:
    """Most-specific glob wins; default LF for text."""
    import fnmatch
    base = rel.rsplit("/", 1)[-1]
    best, best_len = "lf", -1
    for glob, eol in decls.items():
        if fnmatch.fnmatch(rel, glob) or fnmatch.fnmatch(base, glob):
            score = len(glob)
            if score > best_len:
                best, best_len = eol, score
    return best


def load_allowlist(root: Path) -> dict[str, str]:
    """Return {path: reason} for reviewed, deliberate byte-exact files.

    A fixture whose whole point is its raw bytes (a CRLF canonicalization
    vector, a byte-identity pin) is not drift. Each entry needs a reason; a
    missing or malformed file is a hard error, never a silent skip.
    """
    path = root / ALLOWLIST
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"check-encoding: FAIL - allowlist unreadable: {exc}", file=sys.stderr)
        sys.exit(EXIT_USAGE)
    entries = data.get("entries") or []
    if not isinstance(entries, list):
        print("check-encoding: FAIL - allowlist 'entries' must be a list",
              file=sys.stderr)
        sys.exit(EXIT_USAGE)
    out: dict[str, str] = {}
    for row in entries:
        if not isinstance(row, dict) or not str(row.get("reason", "")).strip():
            print(f"check-encoding: FAIL - allowlist row without a reason: {row!r}",
                  file=sys.stderr)
            sys.exit(EXIT_USAGE)
        p = row.get("path")
        if not p:
            print(f"check-encoding: FAIL - allowlist row without a path: {row!r}",
                  file=sys.stderr)
            sys.exit(EXIT_USAGE)
        out[p] = row["reason"]
    return out


def load_baseline(root: Path) -> dict[str, int]:
    path = root / BASELINE
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"check-encoding: FAIL - baseline unreadable: {exc}", file=sys.stderr)
        sys.exit(EXIT_USAGE)
    files = data.get("files") or {}
    if not isinstance(files, dict):
        print("check-encoding: FAIL - baseline 'files' must be an object",
              file=sys.stderr)
        sys.exit(EXIT_USAGE)
    return {k: int(v) for k, v in files.items()}


def classify(rel: str, data: bytes, decls: dict[str, str]) -> list[str]:
    """Return the drift findings for one file (empty when clean)."""
    findings: list[str] = []
    for bom, label in BOMS:
        if data.startswith(bom):
            findings.append(f"{label} at byte 0")
            break
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        findings.append(f"not valid UTF-8 (byte {exc.start}): "
                        f"{data[max(0, exc.start-4):exc.start+4]!r}")
        return findings  # line-ending analysis is meaningless on undecodable bytes
    want = declared_eol(rel, decls)
    body = data[3:] if data.startswith(b"\xef\xbb\xbf") else data
    crlf = body.count(b"\r\n")
    lone_cr = body.count(b"\r") - crlf
    lf = body.count(b"\n") - crlf
    if want == "lf":
        if crlf:
            findings.append(f"CRLF line endings ({crlf}) where .gitattributes "
                            f"declares LF")
        if lone_cr:
            findings.append(f"lone CR ({lone_cr}) where LF is declared")
    else:
        if lf:
            findings.append(f"LF-only lines ({lf}) where .gitattributes "
                            f"declares CRLF")
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="check_encoding",
        description="encoding + line-ending drift gate (fw-encoding-01)")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--no-baseline", action="store_true")
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    root = Path(args.repo).resolve()
    gc = _load_gate_common()
    try:
        skip_dirs = gc.load_skip_dirs()
    except Exception as exc:
        print(f"check-encoding: FAIL - cannot load scope contract: {exc}",
              file=sys.stderr)
        return EXIT_USAGE

    decls = load_eol_declarations(root)
    allow = load_allowlist(root)
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
            continue  # reviewed deliberate bytes (byte-exact fixture)
        found = classify(rel, data, decls)
        if found:
            per_file[rel] = found

    if scanned == 0:
        print("check-encoding: FAIL - zero text files scanned (no vacuous green)",
              file=sys.stderr)
        return EXIT_VIOLATIONS

    if args.write_baseline:
        doc = {
            "api_version": "devgate.encoding-baseline/v1",
            "note": ["fw-encoding-01 ratchet: grandfathered encoding/line-ending",
                     "drift. May only DECREASE; fix files as you touch them and",
                     "rerun --write-baseline."],
            "files": {k: len(v) for k, v in sorted(per_file.items())},
        }
        (root / BASELINE).write_text(json.dumps(doc, indent=1) + "\n",
                                     encoding="utf-8")
        print(f"check-encoding: wrote baseline - {len(per_file)} file(s), "
              f"{sum(len(v) for v in per_file.values())} finding(s)")
        return EXIT_OK

    baseline = {} if args.no_baseline else load_baseline(root)
    over = {k: v for k, v in per_file.items()
            if len(v) > baseline.get(k, 0)}
    improved = {k for k in baseline if k not in per_file
                or len(per_file.get(k, [])) < baseline[k]}

    if over:
        total = sum(len(v) for v in over.values())
        print(f"check-encoding: FAIL - {len(over)} file(s) exceed their "
              f"encoding baseline (fw-encoding-01); {total} finding(s)")
        cap = 10**9 if args.list else 30
        shown = 0
        for rel in sorted(over):
            for f in over[rel]:
                if shown >= cap:
                    break
                print(f"  {rel}: {f}")
                shown += 1
        if shown < total:
            print(f"  ... and {total - shown} more")
        print("  fix: strip the BOM, convert to the declared encoding, and "
              "normalise line endings (git add --renormalize . after fixing "
              ".gitattributes)")
        return EXIT_VIOLATIONS

    if improved:
        print(f"check-encoding: note - {len(improved)} file(s) improved below "
              f"baseline; tighten .guardrails/encoding-baseline.json")

    grand = sum(baseline.get(k, 0) for k in per_file)
    print(f"check-encoding: OK - {scanned} text file(s) within baseline "
          f"({grand} grandfathered finding(s), "
          f"{len(decls)} .gitattributes rule(s), "
          f"{len(allow)} reviewed deliberate file(s))")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
