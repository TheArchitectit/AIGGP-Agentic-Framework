#!/usr/bin/env python3
# spec: fw-charset-01
"""check_charset.py — tracked text must be ASCII-clean (fw-charset-01).

DevGate's tracked text is consumed by terminals, fonts, log pipelines, code
review UIs, and AI agents whose tokenizers and renderers do not all agree on
non-ASCII glyphs. The concrete failure this gate closes: U+00A7 SECTION SIGN
("\u00a7") is a legitimate section marker in the source specs, but it renders as a
dollar-ish glyph in some clients and is not an English-language character — a
reviewer reading "spec 12 \u00a73.2" saw "spec 12 $3.2" and filed it as a defect.
The same class covers curly quotes, arrows, box-drawing, and emoji used in
place of plain English.

The standard: tracked text is ASCII (0x00-0x7F). A reviewed, reason-carrying
allowlist (.guardrails/charset-allowlist.json) preserves typography that
carries structural meaning (dashes, arrows, box-drawing, status glyphs) and
may NARROW the standard but never disable it. The reported defect (U+00A7) is
explicitly DENIED so a later allowlist edit cannot silently reintroduce it.

Fail-closed, non-vacuous:
  * a scan that reads zero files FAILS (no vacuous green);
  * a malformed/absent allowlist FAILS rather than silently banning nothing;
  * the deny list always beats the allow list.

Exit: 0 clean; 1 violations; 2 usage.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_VIOLATIONS = 1
EXIT_USAGE = 2

TEXT_EXTS = frozenset({
    ".md", ".markdown", ".txt", ".rst",
    ".py", ".go", ".rs", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".sh", ".bash", ".zsh",
    ".yml", ".yaml", ".json", ".jsonl", ".toml", ".ini", ".cfg", ".env",
    ".sql", ".proto", ".html", ".css", ".hbs", ".xml", ".csv",
})
TEXT_BASENAMES = frozenset({
    ".gitignore", ".gitattributes", ".editorconfig", "dockerfile", "makefile",
    "license", "notice",
})
ALLOWLIST = Path(".guardrails") / "charset-allowlist.json"
BASELINE = Path(".guardrails") / "charset-baseline.json"

# ASCII replacements offered in the fix hint, keyed by codepoint.
FIX_HINTS = {
    0x00A7: "Sec.", 0x2013: "-", 0x2014: "-", 0x2018: "'", 0x2019: "'",
    0x201C: '"', 0x201D: '"', 0x2026: "...", 0x2192: "->", 0x2190: "<-",
    0x00D7: "x", 0x00A0: " ",
}

# Substitution artifacts (fw-charset-01, added 2026-10-19).
#
# The failure this closes: a sweep that replaces each glyph INDEPENDENTLY
# turns a doubled source token into a doubled replacement. Two section signs
# before a number list became the duplicated-word form in GR specs 11 and 15
# and in OMCP's s27-0 ledger - a typo-looking defect Roger has now reported
# twice. The charset gate could not see it because the output is pure ASCII:
# this gate checks CODEPOINTS, and the replacement word has none to complain
# about.
#
# So the gate that PRESCRIBES the substitution also refuses its degenerate
# output. These are literal-ASCII defects, so the ratchet baseline does NOT
# grandfather them: an artifact is never accepted debt.
SUBSTITUTION_ARTIFACTS = (
    (re.compile(r"\bSec\.\s+Sec\."), "doubled section marker after U+00A7 substitution"),
    (re.compile(r"\b(Section|Figure|Table|Chapter|Clause|Appendix|Article)"
                r"\.\s+\1\."), "doubled cross-reference token"),
    (re.compile(r"\.\.\.\.+"), "doubled ellipsis after U+2026 substitution"),
)


def _load_gate_common():
    here = Path(__file__).resolve()
    for cand in (here.parent, here.parent.parent / "scripts"):
        if (cand / "gate_common.py").is_file():
            sys.path.insert(0, str(cand))
            break
    import gate_common  # noqa: E402
    return gate_common


def load_policy(root: Path):
    """Return (allowed:set[int], denied:set[int]). Missing/invalid = hard error."""
    path = root / ALLOWLIST
    if not path.is_file():
        print(f"check-charset: FAIL - allowlist missing at {ALLOWLIST} "
              f"(a gate that bans nothing is worse than no gate)", file=sys.stderr)
        sys.exit(EXIT_USAGE)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"check-charset: FAIL - allowlist unreadable: {exc}", file=sys.stderr)
        sys.exit(EXIT_USAGE)

    def _cp(value) -> int:
        """Accept 0x-prefixed hex ("0x00A7") or plain int/hex string."""
        if isinstance(value, int):
            return value
        return int(str(value), 0)

    allowed: set[int] = set()
    denied: set[int] = set()

    def _reason(row) -> str:
        r = row.get("reason") if isinstance(row, dict) else None
        if not isinstance(r, str) or not r.strip():
            print(f"check-charset: FAIL - policy row without a reason: {row!r}",
                  file=sys.stderr)
            sys.exit(EXIT_USAGE)
        return r

    for row in data.get("allow", []) or []:
        _reason(row)
        if "codepoint" in row:
            allowed.add(_cp(row["codepoint"]))
        elif "range" in row:
            lo, hi = row["range"]
            allowed.update(range(_cp(lo), _cp(hi) + 1))
        else:
            print(f"check-charset: FAIL - allow row needs codepoint or range: {row!r}",
                  file=sys.stderr)
            sys.exit(EXIT_USAGE)

    for row in data.get("deny", []) or []:
        _reason(row)
        if "codepoint" in row:
            denied.add(_cp(row["codepoint"]))
        elif "range" in row:
            lo, hi = row["range"]
            denied.update(range(_cp(lo), _cp(hi) + 1))
        else:
            print(f"check-charset: FAIL - deny row needs codepoint or range: {row!r}",
                  file=sys.stderr)
            sys.exit(EXIT_USAGE)

    # strict_zero: path prefixes the ratchet baseline may NOT grandfather.
    # The baseline exists to land a standard on a drifted tree without a mass
    # rewrite; it must never become the reason a tree that keeps regressing is
    # exempt. A gate that prescribes a fix also refuses to let its own subject
    # area accumulate debt forever.
    strict_paths: set[str] = set()
    for row in data.get("strict_zero", []) or []:
        _reason(row)
        p = row.get("path") if isinstance(row, dict) else None
        if not isinstance(p, str) or not p.strip():
            print(f"check-charset: FAIL - strict_zero row needs a 'path': {row!r}",
                  file=sys.stderr)
            sys.exit(EXIT_USAGE)
        strict_paths.add(p.strip().strip("/"))

    # A deny entry that is also allowed is a policy contradiction: refuse to run.
    conflict = allowed & denied
    if conflict:
        print("check-charset: FAIL - codepoints both allowed and denied: "
              + ", ".join(f"U+{c:04X}" for c in sorted(conflict)), file=sys.stderr)
        sys.exit(EXIT_USAGE)
    return allowed, denied, strict_paths


def load_baseline(root: Path) -> dict[str, int]:
    """Return {path: grandfathered non-ASCII count}.

    The ratchet idiom (mirrors traceability-ratchet.json): existing debt is
    grandfathered so the standard lands fleet-wide without a mass rewrite
    blocking every repo, but it may only DECREASE. A file exceeding its
    baseline FAILS; a file that dropped below baseline is reported so the
    baseline can be tightened. Missing baseline = zero tolerance (clean tree).
    """
    path = root / BASELINE
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"check-charset: FAIL - baseline unreadable: {exc}", file=sys.stderr)
        sys.exit(EXIT_USAGE)
    files = data.get("files")
    if files is None:
        return {}
    if not isinstance(files, dict):
        print("check-charset: FAIL - baseline 'files' must be an object",
              file=sys.stderr)
        sys.exit(EXIT_USAGE)
    out: dict[str, int] = {}
    for rel, n in files.items():
        try:
            out[rel] = int(n)
        except (TypeError, ValueError):
            print(f"check-charset: FAIL - baseline row {rel!r} not an int",
                  file=sys.stderr)
            sys.exit(EXIT_USAGE)
    return out


def tracked_files(root: Path) -> list[str]:
    r = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        print(f"check-charset: FAIL - git ls-files failed: {r.stderr}",
              file=sys.stderr)
        sys.exit(EXIT_USAGE)
    return [f for f in r.stdout.split("\0") if f]


def is_text(path: str) -> bool:
    p = Path(path)
    return p.suffix.lower() in TEXT_EXTS or p.name.lower() in TEXT_BASENAMES


def is_strict(rel: str, strict_paths: set[str]) -> bool:
    """True when ``rel`` sits inside a strict-zero scope (prefix, path-boundary)."""
    for p in strict_paths:
        if rel == p or rel.startswith(p + "/"):
            return True
    return False


def scan(root: Path, allowed: set[int], denied: set[int], max_report: int,
         baseline: dict[str, int] | None = None,
         strict_paths: set[str] | None = None) -> int:
    gate_common = _load_gate_common()
    try:
        skip_dirs = gate_common.load_skip_dirs()
    except Exception as exc:
        print(f"check-charset: FAIL - cannot load scope contract: {exc}",
              file=sys.stderr)
        return EXIT_USAGE

    baseline = baseline or {}
    files = [f for f in tracked_files(root) if is_text(f)]
    files = [f for f in files
             if not any(part in skip_dirs for part in Path(f).parts)]

    strict_paths = strict_paths or set()
    violations = []
    artifacts = []
    strict_hits: list[tuple[str, int, int, int, str]] = []
    scanned = 0
    per_file: dict[str, int] = {}
    for rel in files:
        try:
            data = (root / rel).read_bytes()
        except OSError:
            continue
        scanned += 1
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            violations.append((rel, 1, 1, 0xFFFD, f"not valid UTF-8: {exc}"))
            per_file[rel] = per_file.get(rel, 0) + 1
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for pat, why in SUBSTITUTION_ARTIFACTS:
                m = pat.search(line)
                if m:
                    artifacts.append((rel, lineno, m.start() + 1,
                                      m.group(0), why))
            for col, ch in enumerate(line, 1):
                cp = ord(ch)
                if cp <= 0x7F:
                    continue
                if cp in denied or (cp not in allowed):
                    violation = (rel, lineno, col, cp, ch)
                    violations.append(violation)
                    per_file[rel] = per_file.get(rel, 0) + 1
                    if is_strict(rel, strict_paths):
                        strict_hits.append(violation)

    if scanned == 0:
        print("check-charset: FAIL - zero text files scanned (no vacuous green)",
              file=sys.stderr)
        return EXIT_VIOLATIONS

    # Ratchet: a file may not exceed its grandfathered baseline.
    over = {rel: n for rel, n in per_file.items()
            if n > baseline.get(rel, 0)}
    improved = {rel: n for rel, n in per_file.items()
                if rel in baseline and n < baseline[rel]}
    # A baselined file that is now clean (or removed) also counts as improved.
    for rel in baseline:
        if rel not in per_file:
            improved[rel] = 0

    # Substitution artifacts first: they are ASCII, so they are never
    # grandfathered by the ratchet baseline and must be reported even when the
    # non-ASCII counts are within budget. Baselines grandfather legacy debt,
    # not defects the standard itself creates.
    if artifacts:
        print(f"check-charset: FAIL - {len(artifacts)} substitution "
              f"artifact(s) (fw-charset-01); the ASCII replacement of a "
              f"doubled source token produced a duplicated word")
        for rel, lineno, col, shown, why in artifacts[:max_report]:
            print(f"  {rel}:{lineno}:{col}  {shown!r}  ({why})")
        print("  fix: replace each source glyph ONCE and rewrite the "
              "reference, e.g. two section signs 3, 5 becomes 'Sec. 3 and "
              "Sec. 5' - never the duplicated-word form. Collapse doubled "
              "tokens before substituting; a per-glyph replace turns one "
              "marker into two words. This gate rejects the doubled form, "
              "including in its own hint text.")
        return EXIT_VIOLATIONS

    # Strict scopes: zero tolerance, the baseline does not apply. Checked
    # BEFORE the ratchet so a grandfathered count cannot mask them.
    if strict_hits:
        print(f"check-charset: FAIL - {len(strict_hits)} non-ASCII codepoint(s) "
              f"inside a strict-zero scope (fw-charset-01); the ratchet "
              f"baseline does not apply to these paths")
        for rel, lineno, col, cp, ch in strict_hits[:max_report]:
            shown = ch if ch.isprintable() else "?"
            hint = FIX_HINTS.get(cp)
            tail = f"  -> {hint!r}" if hint else ""
            print(f"  {rel}:{lineno}:{col}  U+{cp:04X}  {shown!r}{tail}")
        print("  fix: these paths must be ASCII on the first commit; a "
              "baseline entry for them is ignored on purpose")
        return EXIT_VIOLATIONS

    if over:
        print(f"check-charset: FAIL - {len(over)} file(s) exceed their "
              f"charset baseline (fw-charset-01); "
              f"{sum(over.values())} non-ASCII occurrence(s) in new/changed lines")
        for rel, _ in sorted(over.items())[:max_report]:
            for rel2, lineno, col, cp, ch in violations:
                if rel2 != rel:
                    continue
                shown = ch if ch.isprintable() else "?"
                hint = FIX_HINTS.get(cp)
                tail = f"  -> {hint!r}" if hint else ""
                print(f"  {rel}:{lineno}:{col}  U+{cp:04X}  {shown!r}{tail}")
        print("  fix: replace the glyph with its ASCII equivalent "
              "(U+00A7 -> 'Sec.', em/en dash -> '-', arrow -> '->', "
              "curly quotes -> straight, ellipsis -> '...'); add a reasoned "
              "row to .guardrails/charset-allowlist.json only for reviewed "
              "formatting that must stay non-ASCII. Replace each glyph ONCE "
              "and collapse doubled markers: two section signs before a "
              "number list is 'Sec. 3 and Sec. 5', not the doubled form "
              "(which this gate rejects)")
        return EXIT_VIOLATIONS

    if improved:
        print(f"check-charset: note - {len(improved)} file(s) improved below "
              f"their baseline; tighten .guardrails/charset-baseline.json: "
              + ", ".join(sorted(improved)[:8]))

    grandfathered = sum(baseline.get(rel, 0) for rel in per_file)
    print(f"check-charset: OK - {scanned} text file(s) within baseline "
          f"({len(allowed)} allowed / {len(denied)} denied codepoints; "
          f"{grandfathered} grandfathered occurrence(s))")
    return EXIT_OK


def write_baseline(root: Path, allowed: set[int], denied: set[int],
                   strict_paths: set[str] | None = None) -> int:
    """Regenerate the ratchet baseline from the current tree."""
    gate_common = _load_gate_common()
    skip_dirs = gate_common.load_skip_dirs()
    files = [f for f in tracked_files(root) if is_text(f)]
    files = [f for f in files
             if not any(part in skip_dirs for part in Path(f).parts)]
    per: dict[str, int] = {}
    for rel in files:
        try:
            data = (root / rel).read_bytes()
        except OSError:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            per[rel] = per.get(rel, 0) + 1
            continue
        n = sum(1 for line in text.splitlines() for ch in line
                if ord(ch) > 0x7F and (ord(ch) in denied or ord(ch) not in allowed))
        if n and not is_strict(rel, strict_paths or set()):
            per[rel] = n
    doc = {
        "api_version": "devgate.charset-baseline/v1",
        "note": [
            "fw-charset-01 ratchet: grandfathered non-ASCII counts.",
            "May only DECREASE. Fix files as you touch them, then rerun",
            "python3 scripts/check_charset.py --write-baseline to tighten.",
        ],
        "files": dict(sorted(per.items())),
    }
    (root / BASELINE).write_text(json.dumps(doc, indent=1) + "\n",
                                 encoding="utf-8")
    print(f"check-charset: wrote baseline - {len(per)} file(s), "
          f"{sum(per.values())} occurrence(s)")
    return EXIT_OK


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="check_charset",
        description="tracked text must be ASCII-clean (fw-charset-01)")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--max-report", type=int, default=40)
    ap.add_argument("--list", action="store_true",
                    help="print every violation (no cap)")
    ap.add_argument("--no-baseline", action="store_true",
                    help="ignore the ratchet baseline (strict, zero tolerance)")
    ap.add_argument("--write-baseline", action="store_true",
                    help="regenerate the baseline from the current tree and exit")
    args = ap.parse_args()
    root = Path(args.repo).resolve()
    allowed, denied, strict_paths = load_policy(root)
    if args.write_baseline:
        return write_baseline(root, allowed, denied, strict_paths)
    baseline = {} if args.no_baseline else load_baseline(root)
    return scan(root, allowed, denied, 10**9 if args.list else args.max_report,
                baseline, strict_paths)


if __name__ == "__main__":
    sys.exit(main())
