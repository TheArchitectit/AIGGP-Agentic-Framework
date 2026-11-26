#!/usr/bin/env python3
# // spec: spec-state-08
"""spec_state_backfill.py — report-only migration sweep for the spec-state ledger.

Design section 9, first two steps. For every published spec this emits a
candidate row per `EXERCISED` closure cell together with the citations the
acceptance standard needs, and applies that standard:

  1. every implementation path the closure table cites exists at `HEAD`;
  2. a file carrying `spec: <req-id>` exists at `HEAD` and changed inside a
     commit window, and both bounds of that window resolve in reachable
     history;
  3. the two bounds are distinct, ordered commits (the window is a real
     commit's first parent and the commit itself).

A candidate that fails any condition is reported `UNPROVEN` with the failing
condition named. This tool NEVER writes the ledger: design section 9 puts the
report first because "backfilling wrongly is worse than leaving blank", and a
report that silently appended rows would remove the human decision it exists
to inform.

Status-line specs (no closure table) carry no `EXERCISED` cell, so the per-cell
sweep does not reach them. They are reported under `status_line_specs` and
classified by the same standard, because the migration still has to say whether
their terminal prose is provable.

Usage:
  python3 scripts/spec_state_backfill.py [--repo PATH] [--json PATH]

Exit: 0 report produced, 2 usage/config error, 3 nothing scanned.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS / "lib"))
import spec_discovery  # noqa: E402  (sibling module)

EXIT_PASS, EXIT_USAGE, EXIT_NOTHING = 0, 2, 3

STATES = ("EXERCISED", "WIRED", "ABSENT", "NOT_RUN", "DIFFERS")
TERMINAL = "EXERCISED"
# `| `req` (note) | **STATE** | `impl`, ... | `verify`, ... |`
TABLE_ROW = re.compile(
    r"^\|\s*(?:`|\*\*)?([A-Za-z0-9-]+)(?:`|\*\*)?[^|]*\|\s*\**([A-Z_]+)\**\s*"
    r"\|([^|]*)\|([^|]*)\|", re.M)
BACKTICK = re.compile(r"`([^`]+)`")
STATUS_LINE = re.compile(r"^[>\s]*\**Status:\**\s*(.+?)\s*$", re.M)
REQUIREMENTS_HEADING = re.compile(r"^##+\s+Requirements\b", re.M)
TERMINAL_WORD = re.compile(r"^\s*\**\s*(closed|implemented|terminal|complete)\b", re.I)
# A prose citation that cannot be a path: globs, tags, bracket markers.
NOT_A_PATH = re.compile(r"[*\[\]<>]|^v?\d+\.\d+|^[A-Z_]+$")
# A commit-shaped token. Design section 3: a cited SHA is evidence only when
# it resolves in reachable history (the correction that makes 4b69262
# UNPROVEN rather than a row).
COMMIT_SHAPE = re.compile(r"\b[0-9a-f]{7,40}\b")
# A plain-text repository path in a status-line paragraph. Status prose often
# names its implementation without backticks (zig-opengl-engine does), and a
# citation the sweep cannot read is a citation it cannot judge.
PLAIN_PATH = re.compile(
    r"(?<![\w`/])((?:scripts|hub|templates|tests|actions|fleet-manager|"
    r"openspec|\.github)/[A-Za-z0-9_./-]+)")


def git(repo: Path, *args: str) -> tuple[int, str]:
    p = subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout


def rev_resolves(repo: Path, rev: str) -> bool:
    rc, _ = git(repo, "cat-file", "-e", f"{rev}^{{commit}}")
    return rc == 0


def exists_at(repo: Path, rev: str, path: str) -> bool:
    """A cited path exists at `rev` as a blob or a tree (dirs are cited)."""
    p = path.rstrip("/")
    if not p:
        return False
    rc, _ = git(repo, "cat-file", "-e", f"{rev}:{p}")
    if rc == 0:
        return True
    rc, out = git(repo, "ls-tree", "-d", "--name-only", rev, "--", p)
    return rc == 0 and bool(out.strip())


def marked_files(repo: Path, rev: str) -> dict[str, set[str]]:
    """path -> requirement ids marked `spec: <ids>` in that file at `rev`."""
    rc, out = git(repo, "grep", "-l", "-F", "spec:", rev, "--", ".")
    out_map: dict[str, set[str]] = {}
    if rc != 0:
        return out_map
    prefix = f"{rev}:"
    for line in out.splitlines():
        path = line[len(prefix):] if line.startswith(prefix) else line
        rc2, text = git(repo, "show", f"{rev}:{path}")
        if rc2 != 0:
            continue
        ids: set[str] = set()
        for group in spec_discovery.MARKER.findall(text):
            ids.update(spec_discovery.ID.findall(group))
        if ids:
            out_map[path] = ids
    return out_map


def window_for(repo: Path, marked: dict[str, set[str]], req: str,
               cache: dict[str, list[str]]) -> dict | None:
    """Newest commit window whose diff touches a HEAD-resident marked file.

    The landing bound is a real commit that touched such a file; the opening
    bound is its first parent. Both resolve by construction, they are distinct,
    and the diff between them necessarily contains the touched file, which
    still exists at HEAD — the gate's marked-source condition.
    """
    candidates: list[tuple[str, str, list[str]]] = []
    for path, ids in sorted(marked.items()):
        if req not in ids:
            continue
        if path not in cache:
            rc, out = git(repo, "log", "--no-merges", "--format=%H", "--", path)
            cache[path] = out.splitlines() if rc == 0 else []
        for landed in cache[path]:
            rc, parent = git(repo, "rev-parse", f"{landed}^")
            if rc != 0:
                continue  # a root commit has no opening bound
            opened = parent.strip()
            if opened and opened != landed:
                candidates.append((landed, opened, [path]))
    if not candidates:
        return None
    # Newest first: the most recent implementation of the requirement is the
    # honest landing bound for a backfilled row.
    landed, opened, touched = candidates[0]
    return {"opened_commit": opened, "landed_commit": landed,
            "touched_marked_files": touched}


def prose_paths(text: str) -> list[str]:
    """Backticked and plain repository-path tokens cited in status prose."""
    seen: list[str] = []
    tokens = [t.strip() for t in BACKTICK.findall(text)] + \
             [m.group(1) for m in PLAIN_PATH.finditer(text)]
    for t in tokens:
        t = t.rstrip(".,;:")
        if not t or NOT_A_PATH.search(t) or "/" not in t:
            continue
        if t not in seen:
            seen.append(t)
    return seen


def classify_candidate(repo: Path, spec: str, req: str, impl_paths: list[str],
                       verify_paths: list[str], marked: dict[str, set[str]],
                       cache: dict[str, list[str]], cited_text: str = "",
                       commit_text: str = "", strict_paths: bool = True) -> dict:
    reasons: list[str] = []
    existing = [p for p in impl_paths if exists_at(repo, "HEAD", p)]
    missing = [p for p in impl_paths if p not in existing]
    if not impl_paths:
        reasons.append("no implementation path is cited")
    elif strict_paths and missing:
        reasons.append(f"cited implementation path(s) absent at HEAD: {missing}")
    elif not existing:
        reasons.append("no cited path exists at HEAD")
    commit_citations = []
    for sha in sorted(set(COMMIT_SHAPE.findall(commit_text))):
        resolves = rev_resolves(repo, sha)
        commit_citations.append({"sha": sha, "resolves": resolves})
        if not resolves:
            reasons.append(f"cited commit {sha} does not resolve in reachable history")
    marked_for_req = sorted(p for p, ids in marked.items() if req in ids)
    if not marked_for_req:
        reasons.append(f"no file at HEAD carries 'spec: {req}'")
    window = window_for(repo, marked, req, cache) if marked_for_req else None
    if marked_for_req and window is None:
        reasons.append("no resolvable commit window touches a marked file")
    return {
        "citations": {"implementation": impl_paths,
                      "implementation_absent_at_head": missing,
                      "verification": verify_paths,
                      "marked_files": marked_for_req,
                      "commits": commit_citations},
        "window": window,
        "verdict": "ACCEPTED" if not reasons else "UNPROVEN",
        "reasons": reasons,
    }


def sweep(repo: Path, rev: str = "HEAD") -> dict:
    rc, listing = git(repo, "ls-tree", "-r", "--name-only", rev, "--", "openspec/specs")
    if rc != 0:
        return {}
    paths = [p for p in listing.splitlines()
             if re.fullmatch(r"openspec/specs/[^/]+/spec\.md", p)]
    if not paths:
        return {}
    rc, head_sha = git(repo, "rev-parse", rev)
    marked = marked_files(repo, rev)
    cache: dict[str, list[str]] = {}
    candidates, status_specs = [], []
    cell_count = non_terminal = 0

    for path in sorted(paths):
        cap = Path(path).parent.name
        _, text = git(repo, "show", f"{rev}:{path}")
        if not text:
            continue
        preamble = REQUIREMENTS_HEADING.split(text, maxsplit=1)[0]
        status = STATUS_LINE.search(preamble)
        status = status.group(1).strip() if status else None
        reqs = [r for r, block in spec_discovery._requirement_blocks(text)
                if not spec_discovery.DRAFT.search(block)]
        rows = TABLE_ROW.findall(text)
        cells = {r: (state, impl, verify) for r, state, impl, verify in rows
                 if state in STATES}
        # Only closure rows carry a frozen state word. A spec may hold other
        # four-column tables (zig-opengl-engine's pattern catalogue does), and
        # treating those as closure rows would hide the spec from the
        # status-line sweep.
        non_terminal += sum(1 for s, _, _ in cells.values() if s != TERMINAL)

        for req in reqs:
            if req in cells:
                state, impl_col, verify_col = cells[req]
                if state != TERMINAL:
                    continue
                cell_count += 1
                impl = [t.strip() for t in BACKTICK.findall(impl_col)]
                verify = [t.strip() for t in BACKTICK.findall(verify_col)]
                verdict = classify_candidate(repo, cap, req, impl, verify,
                                             marked, cache,
                                             cited_text=impl_col + verify_col,
                                             commit_text=text, strict_paths=True)
                candidates.append({"spec": cap, "req": req,
                                   "cell": TERMINAL, "source": "closure-cell",
                                   **verdict})
            elif not cells and status:
                # A status-line spec: no cell anywhere in it. Prose backticks
                # include consumer-repo paths and tags, so only an existing
                # tracked path counts as an implementation citation; the rest
                # are recorded, not treated as missing implementations.
                impl = prose_paths(preamble)
                verdict = classify_candidate(repo, cap, req, impl, [], marked,
                                             cache, cited_text=preamble,
                                             commit_text=text, strict_paths=False)
                status_specs.append({"spec": cap, "req": req, "status": status,
                                     "terminal_word": bool(TERMINAL_WORD.search(status)),
                                     "source": "status-line", **verdict})
        if not reqs:
            status_specs.append({"spec": cap, "req": None, "status": status,
                                 "source": "unsupported-format",
                                 "citations": {}, "window": None,
                                 "verdict": "UNSUPPORTED",
                                 "reasons": ["no requirement identifiers in the "
                                             "supported format"]})

    accepted = sum(1 for c in candidates if c["verdict"] == "ACCEPTED")
    accepted_status = sum(1 for s in status_specs
                          if s["verdict"] == "ACCEPTED")
    return {
        "schema": "devgate.spec-state-backfill-report/v1",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "head": head_sha.strip(),
        "spec_count": len(paths),
        "summary": {
            "exercised_cells": cell_count,
            "non_terminal_cells": non_terminal,
            "accepted": accepted,
            "unproven": cell_count - accepted,
            "status_line_specs": len(status_specs),
            "status_line_accepted": accepted_status,
        },
        "candidates": candidates,
        "status_line_specs": status_specs,
    }


UNPROVEN_HEADER = """\
# devgate.spec-state-unproven/v1 — migration markers (design section 9).
# One JSON object per line: a requirement whose terminal claim has no proving
# ledger row. Append-only, like the ledger: a later proof is a ledger row, not
# an edit or deletion here. Editing the spec cannot promote a marked
# requirement — proof is a ledger row with two resolved, ordered commits and a
# sealed evidence bundle, which no prose edit produces.
# Comment lines (#) and blank lines are ignored.
"""


def marker_rows(report: dict, exclude: set[tuple[str, str]]) -> list[dict]:
    """One append-only migration marker per unproven terminal requirement."""
    rows: list[dict] = []

    def add(spec: str, req: str, provenance: str, window: dict | None,
            citations: dict, reasons: list[str]) -> None:
        if (spec, req) in exclude:
            return
        if provenance == "accepted":
            reason = ("provenance standard met"
                      + (f" (window {window['opened_commit'][:12]}.."
                         f"{window['landed_commit'][:12]})" if window else "")
                      + "; no sealed evidence bundle is landed, so the claim is unproven")
            citation = (f"{window['opened_commit']}..{window['landed_commit']}"
                        if window else ", ".join(citations.get("implementation", [])))
        else:
            reason = "provenance rejected: " + "; ".join(reasons)
            unresolved = [c["sha"] for c in citations.get("commits", [])
                          if not c["resolves"]]
            absent = citations.get("implementation_absent_at_head") or []
            citation = ", ".join(unresolved) or ", ".join(absent)
        rows.append({"schema": "unproven-v1", "spec": spec, "req": req,
                     "claim": "EXERCISED", "provenance": provenance,
                     "citation": citation, "reason": reason})

    for cand in report["candidates"]:
        provenance = "accepted" if cand["verdict"] == "ACCEPTED" else "rejected"
        add(cand["spec"], cand["req"], provenance, cand.get("window"),
            cand.get("citations", {}), cand.get("reasons", []))
    for entry in report["status_line_specs"]:
        if not entry.get("req") or not entry.get("terminal_word"):
            continue
        provenance = "accepted" if entry["verdict"] == "ACCEPTED" else "rejected"
        add(entry["spec"], entry["req"], provenance, entry.get("window"),
            entry.get("citations", {}), entry.get("reasons", []))
    return rows


def append_markers(path: Path, rows: list[dict]) -> int:
    """Append rows the file does not already carry; never rewrite existing ones."""
    if not path.exists():
        path.write_text(UNPROVEN_HEADER
                        + "".join(json.dumps(r, separators=(",", ":")) + "\n"
                                  for r in rows), encoding="utf-8")
        return len(rows)
    seen: set[tuple[str, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            row = json.loads(line)
        except ValueError as e:
            raise SystemExit(f"{path}: unreadable marker line: {e}")
        if row.get("schema") != "unproven-v1":
            raise SystemExit(f"{path}: row outside schema unproven-v1")
        seen.add((str(row.get("spec")), str(row.get("req"))))
    new = [r for r in rows if (r["spec"], r["req"]) not in seen]
    with path.open("a", encoding="utf-8") as fh:
        for row in new:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    return len(new)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Report-only backfill sweep for the spec-state ledger.")
    ap.add_argument("--repo", default=None, help="repo root (default: by layout)")
    ap.add_argument("--json", default=None, help="write the report to this path")
    ap.add_argument("--unproven-out", default=None,
                    help="append UNPROVEN migration markers to this JSONL path")
    ap.add_argument("--exclude", default="",
                    help="comma-separated spec:req pairs landed as real rows, "
                         "so they carry no unproven marker")
    args = ap.parse_args()

    repo = Path(args.repo).resolve() if args.repo else SCRIPTS.parent
    if not (repo / ".git").exists():
        print(f"spec-state-backfill: {repo} is not a git checkout", file=sys.stderr)
        return EXIT_USAGE
    if not rev_resolves(repo, "HEAD"):
        print("spec-state-backfill: HEAD does not resolve to a commit",
              file=sys.stderr)
        return EXIT_USAGE
    report = sweep(repo)
    if not report:
        print("spec-state-backfill: no published specs found — nothing scanned "
              "is a failure, not an empty report", file=sys.stderr)
        return EXIT_NOTHING

    s = report["summary"]
    print(f"spec-state-backfill: {report['spec_count']} specs at "
          f"{report['head'][:12]}: {s['exercised_cells']} EXERCISED cell(s), "
          f"{s['accepted']} accepted, {s['unproven']} unproven; "
          f"{s['status_line_specs']} status-line/unsupported entr(ies), "
          f"{s['status_line_accepted']} accepted")
    for cand in report["candidates"]:
        if cand["verdict"] != "ACCEPTED":
            print(f"  UNPROVEN {cand['spec']}/{cand['req']}: "
                  f"{'; '.join(cand['reasons'])}")
    for entry in report["status_line_specs"]:
        if entry["verdict"] == "ACCEPTED":
            w = entry["window"]
            print(f"  ACCEPTED(status-line) {entry['spec']}/{entry['req']}: "
                  f"{w['opened_commit'][:12]}..{w['landed_commit'][:12]}")
        elif entry["verdict"] == "UNPROVEN":
            print(f"  UNPROVEN(status-line) {entry['spec']}/{entry['req']}: "
                  f"{'; '.join(entry['reasons'])}")

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2) + "\n",
                                   encoding="utf-8")
        print(f"spec-state-backfill: report written to {args.json}")
    if args.unproven_out:
        exclude = {tuple(pair.split(":", 1)) for pair in args.exclude.split(",")
                   if ":" in pair}
        rows = marker_rows(report, exclude)
        added = append_markers(Path(args.unproven_out), rows)
        print(f"spec-state-backfill: {added} UNPROVEN marker(s) appended to "
              f"{args.unproven_out} ({len(rows)} classified, "
              f"{len(exclude)} landed row(s) excluded)")
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
