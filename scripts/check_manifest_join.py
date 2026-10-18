#!/usr/bin/env python3
# spec: fw-manifest-join-01
"""check_manifest_join.py — declared ⇄ wired names must agree (fw-manifest-join-01).

A capability is declared in one place and wired in another: a tool registered
in a list, a handler in a dispatch switch, an authorization class in a policy
table, a checker in a scanner. Each join is keyed by NAME. When the lists
drift, nothing fails — the item is advertised and unreachable, or wired and
invisible. Both are silent.

Measured instance this gate exists to catch (guardrail-mcp, 2026-10-18):
seven registered MCP tools were absent from the authorization action table, so
every credential was refused by them while `tools/list` still advertised them.
The repo's own guard missed it because it enumerated only what a zero-value
server exposed — 39 of 61 — and reported green over the gap.

This gate is generic: a reviewed manifest (.guardrails/manifest-joins.json)
declares, per join, where the names are declared and where they must appear.
Every join is checked in BOTH directions and the run fails closed.

Why a manifest and not auto-discovery: a language-agnostic gate cannot know
that `Name:` in a Go literal is a registry and `case "x":` is a switch. The
manifest makes that knowledge reviewed data — and a stale manifest (a path
that no longer exists, a join that extracts zero names) is a FAILURE, so it
cannot rot into a no-op the way a regex over prose does.

Exit: 0 every join agrees; 1 a drift or a stale join; 2 usage/manifest error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_USAGE = 2

MANIFEST = Path(".guardrails") / "manifest-joins.json"


def _load_gate_common():
    here = Path(__file__).resolve()
    for cand in (here.parent, here.parent.parent / "scripts"):
        if (cand / "gate_common.py").is_file():
            sys.path.insert(0, str(cand))
            break
    import gate_common  # noqa: E402
    return gate_common


def load_manifest(root: Path) -> list[dict]:
    path = root / MANIFEST
    if not path.is_file():
        print(f"check-manifest-join: FAIL - manifest missing at {MANIFEST}. "
              f"A join gate with no declared joins checks nothing.", file=sys.stderr)
        sys.exit(EXIT_USAGE)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"check-manifest-join: FAIL - manifest unreadable: {exc}", file=sys.stderr)
        sys.exit(EXIT_USAGE)

    joins = data.get("joins")
    if not isinstance(joins, list) or not joins:
        print("check-manifest-join: FAIL - manifest declares no joins", file=sys.stderr)
        sys.exit(EXIT_USAGE)

    for j in joins:
        for key in ("id", "declared", "wired"):
            if not j.get(key):
                print(f"check-manifest-join: FAIL - join missing {key!r}: {j!r}",
                      file=sys.stderr)
                sys.exit(EXIT_USAGE)
        if not j.get("reason"):
            print(f"check-manifest-join: FAIL - join {j.get('id')!r} has no reason; "
                  f"an unexplained join is not reviewable", file=sys.stderr)
            sys.exit(EXIT_USAGE)
    return joins


def _expand(paths: list[str], root: Path) -> list[Path]:
    """Expand repo-relative paths, allowing a directory (all files, recursive)."""
    out: list[Path] = []
    for rel in paths:
        p = root / rel
        if p.is_dir():
            out.extend(sorted(q for q in p.rglob("*") if q.is_file()))
        elif p.is_file():
            out.append(p)
    return out


def extract(paths: list[str], pattern: str, root: Path,
            source: str = "content") -> set[str]:
    """The names this side provides.

    source="content" (default) matches `pattern` group 1 inside each file.
    source="filename" matches `pattern` against each file's basename — the shape
    a join takes when the name is the file itself (a test suite module, a
    migration, a rule file).
    """
    rx = re.compile(pattern, re.MULTILINE)
    out: set[str] = set()
    for p in _expand(paths, root):
        if source == "filename":
            m = rx.match(p.name)
            if m:
                out.add(m.group(1) if m.groups() else p.name)
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in rx.finditer(text):
            val = m.group(1) if m.groups() else m.group(0)
            if val:
                out.add(val)
    return out


def check_join(j: dict, root: Path) -> list[str]:
    """Return drift findings for one join (empty when it agrees)."""
    findings: list[str] = []
    jid = j["id"]

    declared = extract(j["declared"]["paths"], j["declared"]["pattern"], root,
                       j["declared"].get("source", "content"))
    wired = extract(j["wired"]["paths"], j["wired"]["pattern"], root,
                    j["wired"].get("source", "content"))

    # Fail-closed on a stale join: either side extracting nothing means the
    # pattern or the path no longer describes the tree, so agreement is
    # meaningless. This is the vacuity rule; it is not advisory.
    for side, got, spec in (("declared", declared, j["declared"]),
                            ("wired", wired, j["wired"])):
        if not got:
            findings.append(
                f"[{jid}] {side} side extracted ZERO names "
                f"(paths={spec['paths']}, pattern={spec['pattern']!r}) — "
                f"the join is stale; fix the manifest or the tree")
    if findings:
        return findings

    allow = set(j.get("allow_undeclared") or [])

    unwired = sorted(declared - wired - allow)
    if unwired:
        findings.append(
            f"[{jid}] {len(unwired)} declared but not wired (advertised and "
            f"unreachable): {unwired}")

    if j.get("bidirectional", True):
        orphan = sorted(wired - declared - allow)
        if orphan:
            findings.append(
                f"[{jid}] {len(orphan)} wired but not declared (dead wiring): "
                f"{orphan}")

    return findings


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="check_manifest_join",
        description="declared vs wired name joins must agree (fw-manifest-join-01)")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--list", action="store_true", help="print each join's counts")
    args = ap.parse_args()

    root = Path(args.repo).resolve()
    _load_gate_common()  # contract check only; this gate reads explicit paths

    joins = load_manifest(root)
    findings: list[str] = []
    for j in joins:
        got = check_join(j, root)
        findings.extend(got)
        if args.list:
            d = extract(j["declared"]["paths"], j["declared"]["pattern"], root,
                        j["declared"].get("source", "content"))
            w = extract(j["wired"]["paths"], j["wired"]["pattern"], root,
                        j["wired"].get("source", "content"))
            print(f"  {j['id']}: declared={len(d)} wired={len(w)} "
                  f"{'OK' if not got else 'DRIFT'}")

    if findings:
        print(f"check-manifest-join: FAIL - {len(findings)} finding(s) "
              f"across {len(joins)} join(s) (fw-manifest-join-01)")
        for f in findings:
            print(f"  {f}")
        print("  fix: wire the missing names (or delete the dead ones); if a "
              "name is deliberately unwired, add it to that join's "
              "allow_undeclared with the manifest's reason field")
        return EXIT_DRIFT

    print(f"check-manifest-join: OK - {len(joins)} join(s) agree in both "
          f"directions")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
