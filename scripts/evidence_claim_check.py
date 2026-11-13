#!/usr/bin/env python3
# // spec: evc-01, evc-02, evc-03, evc-04, evc-05, evc-06
"""evidence_claim_check.py — mock, stub, or deferral without evidence is not a decision.

WHY THIS EXISTS (measured, not theoretical)
Across 67 days of the digest open-items ledger (`ai-news/nextday-actions.md`,
2026-08-27 -> 2026-11-05), the corpus repeatedly records work that was *declared*
done or blocked without anything a reviewer could check:

    2026-08-26  "TODO/stub/deferred audit — 11 promoted items" (the audit itself is item NEXT-014)
    2026-09-01  "Project Eta's KMS key-rotation landed but is unexercised — confirm a
                 mid-life rotation round-trip test"
    2026-09-02  "N2 mixed-embedding hot-swap — verify artifact stores are single-format
                 or pin before expanding support"
    2026-11-05  "Replace N78's all-caps errata commit subjects with a structured errata
                 file carrying IDs so the failure modes can be counted and gated"

The verify/not-verified family appears on 59/67 days (88%, longest streak 19). The subset
that matters here is narrower and worse: a marker that *looks like* a finished decision.

Three specific shapes, all of which read as complete to a reviewer skimming a diff:
  * `deferred` with no owner, no reason, or no expiry
  * `mock`/`fake` data shipped with no pointer to the real source it stands in for
  * `stub`/`TODO`/`NotImplemented` left in a path that claims to be implemented

This gate makes each one carry a reference a reviewer can follow. It does not forbid any
of them — legitimately deferred and legitimately mocked work is normal. It forbids the
*unevidenced* form.

CONTRACT
  Scan tracked source files for markers, then require an evidence annotation:

    DEFERRED(owner=roger, reason="blocked on PG16 window", review=2027-01-15)
    MOCK(src="docs/fixtures/orders-api.json", why="vendor sandbox unavailable")
    STUB(issue="AIGGP-412", why="interface frozen, impl next sprint")

  A marker with no annotation is a violation. An annotation missing a required field is a
  violation. A `review` date in the past is a violation (deferral expired).

  Markers are only counted in code paths that are NOT explicitly excluded, so a fixtures
  directory or a test double with a real backing file can be declared in the allowlist.

Exit codes: 0 pass | 1 violation | 2 usage/config error | 3 nothing scanned
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

EXIT_OK, EXIT_VIOLATION, EXIT_USAGE, EXIT_EMPTY = 0, 1, 2, 3

# marker shapes this gate governs
MARKERS = {
    "DEFERRED": {"required": ("owner", "reason", "review")},
    "MOCK":     {"required": ("src", "why")},
    "STUB":     {"required": ("issue", "why")},
}

# annotated form: MARKER(field="value", field="value")
ANNOT_RE = re.compile(
    r"\b(DEFERRED|MOCK|STUB)\(([^)\n]{1,400})\)"
)
# A bare marker counts only when it *is* a marker, not when prose mentions the word.
# The 2026-11-05 run against AIGGP's own scripts produced 11 false positives out of 14
# findings — every one a sentence *describing* TODO handling (e.g. "a function body that
# is a TODO"). A gate with that signal-to-noise ratio gets allowlisted into uselessness,
# which is the exact failure `silent-success-scan.sh` exists to catch. So: require the
# token to open a comment, or be followed by a colon/paren, or stand alone as an
# uppercase marker.
BARE_RE = re.compile(
    r"(?:^\s*(?:#|//|/\*|--|;)\s*(TODO|FIXME|XXX)\b(?!,))"   # opens a comment
    r"|\b(TODO|FIXME|XXX)(?=\s*[:()\[])"                     # TODO: / TODO( / TODO[
    r"|\bNotImplementedError\b"                                # a real raise
)
FIELD_RE = re.compile(r'(\w+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^,\s)]+))')

SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".gz",
               ".woff", ".woff2", ".ttf", ".ico", ".mp3", ".wav", ".ogg", ".mp4"}


def parse_fields(body: str) -> dict:
    out = {}
    for m in FIELD_RE.finditer(body):
        val = m.group(2) or m.group(3) or m.group(4) or ""
        out[m.group(1)] = val.strip()
    return out


def load_allow(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    return [l.strip() for l in path.read_text().splitlines()
            if l.strip() and not l.strip().startswith("#")]


def scan(root: Path, allow_globs: list[str]) -> tuple[list[dict], int]:
    import fnmatch
    findings, files = [], 0
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() in SKIP_SUFFIX:
            continue
        rel = str(p.relative_to(root))
        if any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(p.name, g) for g in allow_globs):
            continue
        if "/.git/" in f"/{rel}" or rel.startswith(".git/"):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files += 1
        for lineno, line in enumerate(text.splitlines(), 1):
            # annotated markers
            for m in ANNOT_RE.finditer(line):
                kind = m.group(1)
                fields = parse_fields(m.group(2))
                missing = [f for f in MARKERS[kind]["required"] if not fields.get(f)]
                if missing:
                    findings.append({
                        "file": rel, "line": lineno, "kind": kind,
                        "problem": f"annotation missing {missing}", "text": line.strip()[:100],
                    })
                    continue
                if kind == "DEFERRED":
                    try:
                        rb = dt.date.fromisoformat(fields["review"])
                    except ValueError:
                        findings.append({
                            "file": rel, "line": lineno, "kind": kind,
                            "problem": f"review date unparseable: {fields['review']!r}",
                            "text": line.strip()[:100]})
                        continue
                    if rb < dt.date.today():
                        findings.append({
                            "file": rel, "line": lineno, "kind": kind,
                            "problem": f"deferral expired {rb} — re-decide or remove",
                            "text": line.strip()[:100]})
            # bare markers with no annotation on the line
            if BARE_RE.search(line) and not ANNOT_RE.search(line):
                findings.append({
                    "file": rel, "line": lineno, "kind": "bare",
                    "problem": "marker with no evidence annotation",
                    "text": line.strip()[:100],
                })
    return findings, files


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--allow", type=Path, default=None,
                   help="glob list of paths exempt (fixtures with real backing files)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if not args.root.exists():
        print(f"FATAL: root not found: {args.root}", file=sys.stderr)
        return EXIT_USAGE

    allow = load_allow(args.allow)
    findings, files = scan(args.root, allow)

    if files == 0:
        print("FATAL: no files scanned — refusing a vacuous pass", file=sys.stderr)
        return EXIT_EMPTY

    if args.json:
        print(json.dumps({"files": files, "findings": len(findings),
                          "detail": findings}, indent=1))
    else:
        by_kind = {}
        for f in findings:
            by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1
        summary = ", ".join(f"{k}={v}" for k, v in sorted(by_kind.items())) or "none"
        print(f"files scanned: {files} | unevidenced markers: {len(findings)} ({summary})")
        for f in findings[:40]:
            print(f"  {f['file']}:{f['line']}  [{f['kind']}] {f['problem']}")
            print(f"      {f['text']}")
        if len(findings) > 40:
            print(f"  ... and {len(findings) - 40} more")

    if findings:
        print("\nFAIL: mock/stub/deferred work must carry a followable reference. "
              "Use DEFERRED(owner=,reason=,review=), MOCK(src=,why=), or STUB(issue=,why=).",
              file=sys.stderr)
        return EXIT_VIOLATION
    print("OK: every mock/stub/deferred marker carries evidence")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
