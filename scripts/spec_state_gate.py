#!/usr/bin/env python3
"""spec_state_gate.py — a spec-state transition exists only with a ledger row,
a resolved commit pair, work at the declared location, and sealed evidence.

Why this exists: `openspec/INDEX.md` states it is "Generated, not typed", and
nothing in the tree generated it. `Status: CLOSED` and a closure cell were
assertions a person typed. This gate makes the two records — the spec edit and
the ledger row — have to agree, and requires that a terminal closure be backed
by two resolved commits and a sealed bundle rather than by prose.

Contract: `openspec/changes/add-spec-state-ledger/design.md`.
Row schema and vocabulary are frozen there (sections 1 and 1.1); the row format
is `{"schema":"v1","spec":...,"req":...,"from":...,"to":...,"opened_commit":...,
"landed_commit":...,"tests":[...],"evidence":...,"at":...}`.

Checks (design section 2-6):
  1. changed-by-diff  ==  added-to-ledger      (either side alone fails)
  2. bounding commits resolve, are distinct, and are in strict ancestry order
     with `landed_commit` an ancestor of HEAD
  3. the `opened..landed` diff touches a file carrying `spec: <req-id>`, and
     that file still exists at HEAD
  4. terminal rows carry a sealed bundle that `scripts/evidence-validate.py`
     accepts, with a `passed` record for every test named
  5. a terminal spec has no requirement left non-terminal

Exit codes are frozen (design 1.6):
  0  every reconciled transition is sound
  1  at least one violation
  2  usage or configuration error (bad rev, missing ledger, unusable tree)
  3  nothing scanned (zero spec files, or an empty base..head range) — an empty
     scan is a failure, never a green pass

The gate never runs the tests it reads records for, and never treats a warning
as a pass for a terminal transition: an unresolvable commit, an absent bundle,
or a missing record is a violation.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS / "lib"))
import spec_discovery  # noqa: E402  (sibling module)

EXIT_PASS, EXIT_VIOLATION, EXIT_USAGE, EXIT_NOTHING = 0, 1, 2, 3

STATES = ("EXERCISED", "WIRED", "ABSENT", "NOT_RUN", "DIFFERS")
TERMINAL = "EXERCISED"
ROW_FIELDS = {
    "schema": str, "spec": str, "req": str, "from": str, "to": str,
    "opened_commit": str, "landed_commit": str, "tests": list,
    "evidence": str, "evidence_digest": str, "at": str,
}
OPTIONAL_FIELDS = {"evidence", "evidence_digest"}  # required only with terminal `to`
REQ_ID = re.compile(r"^[A-Za-z0-9-]+$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
# Document-level status: `Status: CLOSED (...)`, `> **Status: DEFERRED** — ...`.
# Only the preamble above `## Requirements` is consulted, so a per-requirement
# "Status: planned" sentence inside a body is never mistaken for the spec's.
STATUS_LINE = re.compile(r"^[>\s]*\**Status:\**\s*(.+?)\s*$", re.M)
REQUIREMENTS_HEADING = re.compile(r"^##+\s+Requirements\b", re.M)
CELL = re.compile(r"^\|\s*(?:`|\*\*)?([A-Za-z0-9-]+)(?:`|\*\*)?[^|]*\|\s*\**([A-Z_]+)\**\s*\|", re.M)
TERMINAL_WORD = re.compile(r"^\s*\**\s*(closed|implemented|terminal|complete)\b", re.I)


def git(repo: Path, *args: str) -> tuple[int, str]:
    p = subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout


def die(message: str, code: int) -> int:
    print(f"spec-state: {message}", file=sys.stderr)
    return code


def rev_resolves(repo: Path, rev: str) -> bool:
    rc, _ = git(repo, "cat-file", "-e", f"{rev}^{{commit}}")
    return rc == 0


def is_ancestor(repo: Path, older: str, newer: str) -> bool:
    rc, _ = git(repo, "merge-base", "--is-ancestor", older, newer)
    return rc == 0


def spec_files_at(repo: Path, rev: str) -> list[str]:
    """Published specs only: openspec/specs/<cap>/spec.md.

    Change packages are excluded on purpose: their specs are deltas whose
    requirement text changes while a change is in flight, and a transition is a
    property of a published spec.
    """
    rc, out = git(repo, "ls-tree", "-r", "--name-only", rev, "--", "openspec/specs")
    if rc != 0:
        return []
    return [p for p in out.splitlines() if re.fullmatch(r"openspec/specs/[^/]+/spec\.md", p)]


def read_at(repo: Path, rev: str, path: str) -> str:
    rc, out = git(repo, "show", f"{rev}:{path}")
    return out if rc == 0 else ""


def spec_states(text: str) -> tuple[dict[str, str], str | None]:
    """(requirement -> cell value, spec Status line) for one spec file.

    A requirement with no closure cell is absent from the dict; the returned
    Status line is the fallback authority those specs use. Both are inputs to
    change detection, so editing either marks the requirement changed.
    """
    preamble = REQUIREMENTS_HEADING.split(text, maxsplit=1)[0]
    m = STATUS_LINE.search(preamble)
    return dict(CELL.findall(text)), (m.group(1).strip() if m else None)


def tree_states(repo: Path, rev: str) -> tuple[dict[tuple[str, str], str], dict[str, str]]:
    """(capability, req) -> signature; capability -> Status line.

    A requirement's signature combines both authorities the design names — its
    closure cell and its spec's `Status:` line — so editing either one marks the
    requirement changed. It is `cell:<STATE>|status:<line>`, `cell:<STATE>`,
    `status:<line>`, or `absent` when the spec gives it neither.
    """
    signatures: dict[tuple[str, str], str] = {}
    statuses: dict[str, str] = {}
    for path in spec_files_at(repo, rev):
        cap = Path(path).parent.name
        text = read_at(repo, rev, path)
        cells, status = spec_states(text)
        if status is not None:
            statuses[cap] = status
        for req, block in spec_discovery._requirement_blocks(text):
            if spec_discovery.DRAFT.search(block):
                continue  # SGA-02: an unreviewed draft is not a requirement yet
            parts = ([f"cell:{cells[req]}"] if req in cells else []) + \
                    ([f"status:{status}"] if status else [])
            signatures[(cap, req)] = "|".join(parts) or "absent"
    return signatures, statuses


def ledger_rows(repo: Path, rev: str, ledger: str) -> list[dict]:
    rc, out = git(repo, "show", f"{rev}:{ledger}")
    if rc != 0:
        return []
    rows = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rows.append(json.loads(line))
    return rows


def row_key(row: dict) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"))


def cell_of(signature: str) -> str | None:
    """The closure-cell state inside a composite signature, or None."""
    for part in signature.split("|"):
        if part.startswith("cell:"):
            return part[len("cell:"):]
    return None


def validate_row(row: dict, index: int) -> list[str]:
    where = f"row {index}"
    problems = []
    unknown = sorted(set(row) - set(ROW_FIELDS))
    if unknown:
        problems.append(f"{where}: unknown field(s) {unknown} — schema v1 is frozen")
    for field, ftype in ROW_FIELDS.items():
        if field not in row:
            if field not in OPTIONAL_FIELDS:
                problems.append(f"{where}: missing required field {field!r}")
        elif not isinstance(row[field], ftype) or (ftype is str and not row[field].strip()):
            problems.append(f"{where}: field {field!r} must be a non-empty {ftype.__name__}")
    if problems:
        return problems
    if row["schema"] != "v1":
        problems.append(f"{where}: schema must be exactly 'v1', got {row['schema']!r}")
    if row["to"] not in STATES:
        problems.append(f"{where}: 'to' must be one of {STATES}, got {row['to']!r}")
    if row["from"] != "OPEN" and row["from"] not in STATES:
        problems.append(f"{where}: 'from' must be 'OPEN' or one of {STATES}, got {row['from']!r}")
    if row["to"] == row["from"]:
        problems.append(f"{where}: 'from' equals 'to' ({row['to']}) — not a transition")
    if not REQ_ID.fullmatch(row["req"]):
        problems.append(f"{where}: 'req' {row['req']!r} is not a requirement ID")
    if not all(isinstance(t, str) and t.strip() for t in row["tests"]):
        problems.append(f"{where}: 'tests' must contain non-empty strings")
    if row["to"] == TERMINAL and not row["tests"]:
        problems.append(f"{where}: terminal transition names no test — nothing exercises it")
    if row["to"] == TERMINAL:
        for field in ("evidence", "evidence_digest"):
            if field not in row:
                problems.append(f"{where}: terminal transition carries no {field!r} — no sealed bundle")
    if "evidence_digest" in row and not DIGEST.fullmatch(row["evidence_digest"]):
        problems.append(f"{where}: 'evidence_digest' must be 'sha256:' + 64 lowercase hex")
    return problems


def marked_source(repo: Path, opened: str, landed: str, req: str) -> str | None:
    """None when the window touches a HEAD-resident file carrying the marker."""
    rc, out = git(repo, "diff", "--name-only", f"{opened}..{landed}")
    if rc != 0:
        return f"cannot diff {opened}..{landed}"
    touched = [p for p in out.splitlines() if p.strip()]
    if not touched:
        return f"{opened[:12]}..{landed[:12]} touches no file at all"
    for path in touched:
        rc, _ = git(repo, "cat-file", "-e", f"HEAD:{path}")
        if rc != 0:
            continue  # the touched file was deleted later; it cannot carry the marker now
        text = read_at(repo, "HEAD", path)
        for group in spec_discovery.MARKER.findall(text):
            if req in spec_discovery.ID.findall(group):
                return None
    return (f"no file changed in {opened[:12]}..{landed[:12]} carries "
            f"'spec: {req}' and still exists at HEAD")


def evidence_problem(repo: Path, bundle: str, expected: str, tests: list[str]) -> str | None:
    """None when the bundle validates against the row's digest and every named
    test has a passed record."""
    bdir = repo / bundle
    if not bdir.is_dir():
        return f"evidence bundle {bundle!r} does not exist"
    p = subprocess.run([sys.executable, str(SCRIPTS / "evidence-validate.py"),
                        str(bdir), "--expected", expected],
                       cwd=str(repo), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode == 30:
        return f"evidence-validate.py could not run on {bundle!r} (usage): {(p.stderr or p.stdout).strip()[:200]}"
    if p.returncode != 0:
        return f"evidence-validate.py rejected {bundle!r} (exit {p.returncode}): {(p.stderr or p.stdout).strip()[:200]}"
    records_path = bdir / "tests.json"
    if not records_path.is_file():
        return f"{bundle!r} carries no tests.json — a row's tests must be sealed records"
    manifest_path = bdir / "evidence-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = json.loads(records_path.read_text(encoding="utf-8"))["tests"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        return f"{bundle!r} test records unreadable: {e}"
    sealed = {o.get("path") for o in manifest.get("objects", []) if isinstance(o, dict)}
    if "tests.json" not in sealed:
        return f"{bundle!r} tests.json is not a sealed manifest object — an unsealed record is a claim about the bundle, not part of it"
    for test in tests:
        if test not in records:
            return f"{bundle!r} has no record for test {test!r}"
        if str(records[test]) != "passed":
            return f"{bundle!r} records test {test!r} as {records[test]!r}, not 'passed'"
    return None


def reconcile(repo: Path, base: str, head: str, ledger: str) -> list[str]:
    violations: list[str] = []

    base_sig, _ = tree_states(repo, base)
    head_sig, head_status = tree_states(repo, head)
    if not head_sig:
        return ["no published specs found at HEAD — an empty scan is a failure, not a pass"]
    for path in spec_files_at(repo, head):
        text = read_at(repo, head, path)
        ids = [r for r, block in spec_discovery._requirement_blocks(text)
               if not spec_discovery.DRAFT.search(block)]
        if not ids:
            violations.append(
                f"{Path(path).parent.name}: no requirement identifiers in the supported "
                f"format — reported as unsupported, never as nothing to check")
    changed = {k for k in set(base_sig) | set(head_sig)
               if base_sig.get(k, "absent") != head_sig.get(k, "absent")}

    base_rows = ledger_rows(repo, base, ledger)
    head_rows = ledger_rows(repo, head, ledger)
    base_keys = {row_key(r) for r in base_rows}
    head_keys = {row_key(r) for r in head_rows}
    added = [r for r in head_rows if row_key(r) not in base_keys]
    removed = [r for r in base_rows if row_key(r) not in head_keys]

    for i, row in enumerate(added):
        problems = validate_row(row, i)
        if problems:
            violations.extend(problems)
            continue  # a row that is not schema-valid cannot be followed further
        key = (row["spec"], row["req"])
        if key not in changed:
            violations.append(
                f"row {i}: ledger adds {row['spec']}/{row['req']} -> {row['to']} but the spec's "
                f"state did not change between {base[:12]} and {head[:12]} — a row with no state edit")
        else:
            before = cell_of(base_sig.get(key, ""))
            after = cell_of(head_sig.get(key, ""))
            if before is not None and before != row["from"]:
                violations.append(
                    f"row {i}: 'from' says {row['from']} but the cell read {before} at "
                    f"{base[:12]} — the row and the spec disagree about the prior state")
            elif before is None and row["from"] != "OPEN":
                violations.append(
                    f"row {i}: 'from' says {row['from']} but {key[0]}/{key[1]} had no closure cell "
                    f"at {base[:12]} — a prior state must be OPEN when no cell existed")
            if after is not None and after != row["to"]:
                violations.append(
                    f"row {i}: 'to' says {row['to']} but the cell reads {after} at "
                    f"{head[:12]} — the row and the spec disagree about the new state")
        opened, landed = row["opened_commit"], row["landed_commit"]
        if not rev_resolves(repo, opened):
            violations.append(f"row {i}: opened_commit {opened!r} does not resolve")
            continue
        if not rev_resolves(repo, landed):
            violations.append(f"row {i}: landed_commit {landed!r} does not resolve")
            continue
        if opened == landed:
            violations.append(f"row {i}: opened_commit equals landed_commit ({opened[:12]}) — a transition must span two commits")
            continue
        if not is_ancestor(repo, opened, landed):
            violations.append(f"row {i}: opened_commit {opened[:12]} is not an ancestor of landed_commit {landed[:12]}")
            continue
        if not is_ancestor(repo, landed, head):
            violations.append(f"row {i}: landed_commit {landed[:12]} is not an ancestor of {head[:12]}")
            continue
        problem = marked_source(repo, opened, landed, row["req"])
        if problem:
            violations.append(f"row {i}: {problem}")
            continue
        if row["to"] == TERMINAL:
            problem = evidence_problem(repo, row["evidence"], row["evidence_digest"], row["tests"])
            if problem:
                violations.append(f"row {i}: {problem}")

    ledgered = {(row["spec"], row["req"]) for row in added}
    for cap, req in sorted(changed - ledgered):
        violations.append(
            f"{cap}/{req}: state changed between {base[:12]} and {head[:12]} with no ledger row — "
            f"a transition without authority")

    for i, row in enumerate(removed):
        violations.append(
            f"removed row {i}: {row.get('spec')}/{row.get('req')} — the ledger is append-only; "
            f"a correction is a new row, never a deletion")

    for cap, status in sorted(head_status.items()):
        if not status or not TERMINAL_WORD.search(status):
            continue
        non_terminal = [req for (c, req), sig in head_sig.items()
                        if c == cap and "cell:" in sig
                        and f"cell:{TERMINAL}" not in sig.split("|")]
        if non_terminal:
            violations.append(
                f"{cap}: Status line says terminal ({status!r}) while {len(non_terminal)} "
                f"requirement(s) are not EXERCISED: {sorted(non_terminal)[:5]}")
    return violations


def main() -> int:
    ap = argparse.ArgumentParser(description="Reconcile spec-state transitions against the ledger.")
    ap.add_argument("--repo", default=None, help="repo root (default: this script's repo, by layout)")
    ap.add_argument("--base", default="HEAD^", help="base revision (default HEAD^)")
    ap.add_argument("--head", default="HEAD", help="head revision (default HEAD)")
    ap.add_argument("--ledger", default="openspec/state-ledger.jsonl", help="ledger path")
    args = ap.parse_args()

    repo = Path(args.repo).resolve() if args.repo else SCRIPTS.parent
    if not (repo / ".git").exists():
        return die(f"{repo} is not a git checkout", EXIT_USAGE)
    for rev in (args.base, args.head):
        if not rev_resolves(repo, rev):
            return die(f"revision {rev!r} does not resolve to a commit", EXIT_USAGE)
    rc, out = git(repo, "rev-list", "--count", f"{args.base}..{args.head}")
    if rc != 0:
        return die(f"cannot compute the range {args.base}..{args.head}", EXIT_USAGE)

    violations = reconcile(repo, args.base, args.head, args.ledger)
    if not violations:
        print(f"spec-state: OK — {args.base}..{args.head} reconciled "
              f"({out.strip()} commit(s))")
        return EXIT_PASS
    if any("no published specs found" in v for v in violations):
        for v in violations:
            print(f"spec-state: {v}", file=sys.stderr)
        return EXIT_NOTHING
    for v in violations:
        print(f"spec-state: VIOLATION — {v}", file=sys.stderr)
    return EXIT_VIOLATION


if __name__ == "__main__":
    sys.exit(main())
