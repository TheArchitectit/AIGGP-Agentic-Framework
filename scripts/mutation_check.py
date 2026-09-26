#!/usr/bin/env python3
"""mutation_test.py — controlled mutation testing for verification strength.

A green test suite is meaningless if deliberately broken production code can
stay green. This tool introduces small, controlled defects into a source file
one at a time, runs the test command against each mutant, and reports whether
the suite DETECTED the defect (test failed) or the mutant SURVIVED (tests
stayed green — a verification blind spot).

Safety contract:
  - the original file is backed up and restored in a `finally` block; a
    killed run must never leave a mutant on disk;
  - mutants run in a subprocess with a hard timeout — a mutant that hangs
    (e.g. inverted loop condition) is KILLED_BY_TIMEOUT, not a wedge;
  - the tool refuses to operate on a file that is not committed clean when
    run inside a git work tree (mutating uncommitted work destroys it).

Self-check (--self-check): the tool mutates a fixture whose behavior is
known and verifies it would report the expected statuses. A mutation tool
that silently misreports is itself an evaluator integrity failure.

Exit codes:
  0  all mutants killed (or none generated) — suite detected every defect
  1  at least one mutant SURVIVED — verification blind spot found
  2  at least one mutant was KILLED_BY_TIMEOUT
  30 usage / setup error
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

EXIT_CLEAN = 0
EXIT_SURVIVED = 1
EXIT_TIMEOUT = 2
EXIT_USAGE = 30

# --- mutation operators ------------------------------------------------------
#
# Each operator: (name, compiled regex, replacement template). Group 1 of the
# match is re-emitted via the template so line/column context stays intact.
# Operators deliberately mimic the defect classes from the audit methodology:
# inverted conditionals, off-by-one boundaries, altered return values,
# disabled error paths.

_COMPARISON_SWAPS = [
    ("==", "!="), ("!=", "=="),
    (">=", "<"), ("<=", ">"), (">", "<="), ("<", ">="),
]
# Build a single alternation, longest first so >= is not eaten by >.
_CMP_RE = re.compile(r"(>=|<=|==|!=|>|<)")

_BOOL_RE = re.compile(r"\b(and|or)\b")

_CONSTANT_RE = re.compile(r"\b(return True|return False)\b")

# Removing a raise leaves the error path silently swallowed.
_RAISE_RE = re.compile(r"^(\s*)raise (\w+)(\(.*\))?\s*$", re.MULTILINE)


def _swap_comparison(m: re.Match) -> str:
    token = m.group(0)
    for a, b in _COMPARISON_SWAPS:
        if token == a:
            return b
    return token


def _excluded_ranges(source: str) -> list:
    """Character ranges where mutations are meaningless: comments and
    docstrings. Mutating them produces EQUIVALENT mutants — reported blind
    spots that cannot be killed — which trains operators to ignore the
    report (evaluator integrity: the tool must not fabricate findings)."""
    import ast
    ranges = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef,
                             ast.ClassDef, ast.Module)):
            doc = ast.get_docstring(node, clean=False)
            if doc and node.body and isinstance(node.body[0], ast.Expr):
                expr = node.body[0]
                if isinstance(expr.value, ast.Constant) and \
                        isinstance(expr.value.value, str):
                    ranges.append((expr.value.lineno, expr.value.end_lineno))
    ranges_chars = []
    lines = source.splitlines(keepends=True)
    for start, end in ranges:
        s = sum(len(l) for l in lines[:start - 1])
        e = s + sum(len(l) for l in lines[start - 1:end])
        ranges_chars.append((s, e))
    # Comment-only spans: from an unquoted # to end of line.
    for m in re.finditer(r"#[^\n]*", source):
        ranges_chars.append((m.start(), m.end()))
    return ranges_chars


def _in_ranges(pos: int, ranges: list) -> bool:
    return any(s <= pos < e for s, e in ranges)


def mutations_for(source: str) -> list:
    """Generate (name, mutated_source) pairs. One defect per mutant.
    Comment/docstring positions are excluded: mutating them yields
    equivalent mutants and a self-defeating report."""
    out = []
    excluded = _excluded_ranges(source)

    def line_of(pos: int) -> int:
        return source.count("\n", 0, pos) + 1

    def add(name, pos, s):
        if s != source and not _in_ranges(pos, excluded):
            out.append((f"{name}@L{line_of(pos)}", s))

    # 1. comparison operator swaps (incl. boundary off-by-one)
    for m in _CMP_RE.finditer(source):
        mutated = source[:m.start()] + _swap_comparison(m) + source[m.end():]
        add(f"comparison:{m.group(0)}->{_swap_comparison(m)}", m.start(), mutated)

    # 2. boolean operator flips
    for m in _BOOL_RE.finditer(source):
        flipped = "or" if m.group(1) == "and" else "and"
        mutated = source[:m.start()] + flipped + source[m.end():]
        add(f"bool:{m.group(1)}->{flipped}", m.start(), mutated)

    # 3. constant return flips
    for m in _CONSTANT_RE.finditer(source):
        flipped = "return False" if m.group(1) == "return True" else "return True"
        mutated = source[:m.start()] + flipped + source[m.end():]
        add(f"constant:{m.group(1)}->{flipped}", m.start(), mutated)

    # 4. raise-removal (error path disabled)
    for m in _RAISE_RE.finditer(source):
        mutated = source[:m.start()] + m.group(1) + "pass  # mutant: raise removed" + source[m.end():]
        add("raise-removed:" + m.group(2), m.start(), mutated)

    return out


class _Restore:
    """Guarantees the original bytes come back — even across SIGKILL.

    A sidecar backup (<target>.mutation-backup) is written BEFORE the
    first mutant and removed after restore. A previous run killed hard
    (power loss, OOM, Ctrl-Backslash) leaves the sidecar behind; the next run
    detects it, restores the original, and reports the incident instead
    of mutating on top of an unknown file state.
    """

    BACKUP_SUFFIX = ".mutation-backup"

    def __init__(self, path: Path):
        self.path = path
        self.backup = path.with_name(path.name + self.BACKUP_SUFFIX)
        self.original = path.read_bytes()

    @classmethod
    def recover(cls, path: Path) -> bool:
        """Restore from a stale sidecar if present. True when a recovery
        happened."""
        backup = path.with_name(path.name + cls.BACKUP_SUFFIX)
        if not backup.exists():
            return False
        original = backup.read_bytes()
        current = path.read_bytes()
        path.write_bytes(original)
        backup.unlink()
        if current != original:
            print(f"mutation_check: RECOVERED {path.name} from a stale "
                  f"backup — the previous run was killed with a mutant on "
                  f"disk (disk state was NOT the original; restored "
                  f"{len(original)} bytes)", file=sys.stderr)
        return True

    def __enter__(self):
        self.backup.write_bytes(self.original)
        return self

    def write(self, text: str):
        self.path.write_text(text, encoding="utf-8")

    def __exit__(self, exc_type, exc, tb):
        self.path.write_bytes(self.original)
        self.backup.unlink(missing_ok=True)
        return False


def _git_clean(path: Path) -> bool:
    """True when path has no uncommitted changes (best effort)."""
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain", "--", str(path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            cwd=str(path.parent))
    except (OSError, subprocess.TimeoutExpired):
        return True  # not a git tree or git unavailable — nothing to protect
    return r.returncode != 0 or not r.stdout.strip()


def run_mutations(target: Path, test_cmd: list, timeout: float,
                  max_mutants: int, workdir: str) -> list:
    """Apply every generated mutant, run the test command, classify results."""
    # Crash-safety first: a previous killed run may have left a mutant on
    # disk — recover the original before reading anything.
    if _Restore.recover(target):
        source = target.read_text(encoding="utf-8")
    else:
        source = target.read_text(encoding="utf-8")
    muts = mutations_for(source)
    if max_mutants and len(muts) > max_mutants:
        muts = muts[:max_mutants]
    results = []
    with _Restore(target) as restore:
        for name, mutated in muts:
            restore.write(mutated)
            try:
                r = subprocess.run(
                    test_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=timeout, cwd=workdir)
                status = "KILLED" if r.returncode != 0 else "SURVIVED"
            except subprocess.TimeoutExpired:
                status = "KILLED_BY_TIMEOUT"
            except OSError as e:
                status = f"TEST_CMD_ERROR:{e}"
            results.append({"mutation": name, "status": status})
        # `finally`-grade guarantee: leaving the with-block restores original.
    return results


def self_check() -> bool:
    """Evaluator integrity for the mutation tool itself.

    Runs the full pipeline against a known fixture: a function with a
    boundary comparison and its test. The tool must (a) generate the
    expected boundary mutant, (b) report it KILLED by the fixture's test.
    If the tool misreports a deliberately introduced defect, it is defective.
    """
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        (tdp / "victim.py").write_text(
            "def check(n):\n"
            "    return n >= 10\n",
            encoding="utf-8")
        (tdp / "test_victim.py").write_text(
            "from victim import check\n"
            "def test_boundary():\n"
            "    assert check(10) is True\n"
            "    assert check(9) is False\n",
            encoding="utf-8")
        target = tdp / "victim.py"
        results = run_mutations(
            target, [sys.executable, "-m", "pytest", "-x", "-q",
                     "test_victim.py"],
            timeout=120, max_mutants=0, workdir=td)
        by_name = {r["mutation"]: r["status"] for r in results}
        ok = True
        # The >= -> < boundary flip must exist and MUST be caught.
        boundary = [n for n in by_name if n.startswith("comparison:>=-><")]
        if not boundary:
            print("SELF-CHECK FAIL: boundary mutant was not generated")
            ok = False
        elif any(by_name[n] != "KILLED" for n in boundary):
            print("SELF-CHECK FAIL: boundary mutant SURVIVED — "
                  "the tool or fixture is broken")
            ok = False
        # True/False flips on `return n >= 10`? none — but the comparison
        # mutants generated must not all be misreported as SURVIVED.
        if results and all(r["status"] == "SURVIVED" for r in results):
            print("SELF-CHECK FAIL: every mutant survived; tool misreporting")
            ok = False
        if ok:
            print("mutation self-check: OK —"
                  f" {len(results)} mutants generated, boundary mutant killed")
        return ok


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="mutation_test",
        description="verify that the test suite detects deliberate defects")
    ap.add_argument("--target", help="source file to mutate")
    ap.add_argument("--tests", help="test command to run per mutant "
                                    "(default: pytest -x -q <target's tests>)")
    ap.add_argument("--timeout", type=float, default=300.0,
                    help="per-mutant test timeout seconds (default 300)")
    ap.add_argument("--max-mutants", type=int, default=0,
                    help="cap the number of mutants (0 = no cap)")
    ap.add_argument("--workdir", default=".",
                    help="working directory for the test command")
    ap.add_argument("--self-check", action="store_true",
                    help="verify the tool itself detects a known defect")
    ap.add_argument("--json-out",
                    help="write the full mutant report as JSON here")
    args = ap.parse_args()

    if args.self_check:
        return EXIT_CLEAN if self_check() else EXIT_USAGE

    if not args.target:
        ap.error("--target is required (or use --self-check)")
    target = Path(args.target)
    if not target.is_file():
        print(f"mutation_test: target not found: {target}", file=sys.stderr)
        return EXIT_USAGE
    if not _git_clean(target):
        print(f"mutation_test: refusing to mutate {target}: it has "
              f"uncommitted changes (restore would destroy work)",
              file=sys.stderr)
        return EXIT_USAGE

    test_cmd = (args.tests.split() if args.tests
                else [sys.executable, "-m", "pytest", "-x", "-q",
                      str(target.parent)])
    results = run_mutations(target, test_cmd, args.timeout,
                            args.max_mutants, args.workdir)

    if args.json_out:
        Path(args.json_out).write_text(json.dumps({
            "target": str(target), "results": results,
        }, indent=1), encoding="utf-8")

    survived = [r for r in results if r["status"] == "SURVIVED"]
    timed_out = [r for r in results if r["status"] == "KILLED_BY_TIMEOUT"]
    killed = [r for r in results if r["status"] == "KILLED"]
    print(f"mutation_test: {len(results)} mutants — "
          f"{len(killed)} killed, {len(survived)} SURVIVED, "
          f"{len(timed_out)} killed-by-timeout")
    for r in survived:
        print(f"  BLIND SPOT: {r['mutation']} survived the test suite")
    if survived:
        return EXIT_SURVIVED
    if timed_out:
        return EXIT_TIMEOUT
    return EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
