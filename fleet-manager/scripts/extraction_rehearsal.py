# spec: repo-005-01, repo-005-02
"""Extraction rehearsal (REPO-005, box 1.3).

Proves two things, each in a throwaway copy of the tree so the real checkout is
never touched:

**Phase A — the boundary package stands up alone.** Copy `fleet-manager/` into
an empty workspace, copy in *only* the declared build inputs (the open-core
modules the package is allowed to import), and run the package's own tests
there. If a test reaches for any other part of the repository, this fails —
which is the point: a hidden repository-relative import is invisible while the
whole tree is present.

**Phase B — the open core stands up without the boundary.** Copy the
repository *without* `fleet-manager/`, then collect the entire core test suite
and run the pattern scan. Nothing in the core may need the boundary to exist.

The declared build inputs are the same set the contract suite pins
(`TestCoreImportSurfacePinned`), and a test in that suite fails if the two
drift apart.

Usage:
    python3 fleet-manager/scripts/extraction_rehearsal.py [--source .] [--keep]

Exit codes: 0 rehearsed and green, 1 a phase failed, 2 the rehearsal itself
could not run (missing source, unreadable manifest).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BOUNDARY_ROOT = "fleet-manager"

# Published build inputs: the open-core files the boundary package may import.
# Kept in lockstep with fleet_manager's pinned import surface by a test.
DECLARED_BUILD_INPUTS = (
    "hub/__init__.py",
    "hub/coherence/__init__.py",
    "hub/coherence/schemacheck.py",
)

IGNORE = shutil.ignore_patterns(
    ".git", "node_modules", "__pycache__", ".venv", ".pytest_cache",
    "*.pyc", ".mypy_cache")


def _run(cmd, cwd, env=None):
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          env=env)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _manifest_paths(source: Path) -> list:
    manifest = source / BOUNDARY_ROOT / "manifest.json"
    try:
        doc = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[rehearsal] cannot read {manifest}: {exc}", file=sys.stderr)
        raise SystemExit(2)
    return doc.get("paths", [])


def phase_a(source: Path, workspace: Path) -> list:
    """The boundary package, alone plus its declared build inputs."""
    failures = []
    target = workspace / BOUNDARY_ROOT
    shutil.copytree(source / BOUNDARY_ROOT, target, ignore=IGNORE)
    for rel in DECLARED_BUILD_INPUTS:
        dest = workspace / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / rel, dest)

    # Anything else from open core must be absent, or "it compiled here" would
    # not mean anything: a test could import a module that happened to sit next
    # to the build inputs.
    unexpected = []
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(workspace).as_posix()
        if not rel.startswith(f"{BOUNDARY_ROOT}/"):
            unexpected.append(rel)
    unexpected.sort()
    if unexpected != sorted(DECLARED_BUILD_INPUTS):
        failures.append(
            "phase A workspace holds files beyond the declared build inputs: "
            f"{unexpected}")

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(target), str(workspace)])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("SPEC_AUDIT_OPENSPEC_BIN", None)
    rc, out = _run([sys.executable, "-m", "pytest", "fleet-manager/tests",
                    "-q"], workspace, env)
    print(f"[rehearsal] phase A: pytest in the extracted copy -> exit {rc}")
    if rc != 0:
        failures.append("phase A: the package's tests do not pass when "
                        "extracted\n" + out.strip()[-2000:])
    return failures


def phase_b(source: Path, workspace: Path) -> list:
    """Open core, with the boundary absent."""
    failures = []
    shutil.copytree(source, workspace, ignore=IGNORE,
                    ignore_dangling_symlinks=True,
                    dirs_exist_ok=True)
    boundary = workspace / BOUNDARY_ROOT
    if boundary.exists():
        shutil.rmtree(boundary)
    if (workspace / BOUNDARY_ROOT).exists():
        failures.append("phase B: the boundary is still present")

    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    rc, out = _run([sys.executable, "-m", "pytest", "tests/",
                    "--collect-only", "-q"], workspace, env)
    print(f"[rehearsal] phase B: core suite collection -> exit {rc}")
    if rc != 0:
        failures.append("phase B: the core test suite cannot be collected "
                        "without the boundary\n" + out.strip()[-2000:])
    else:
        collected = [line for line in out.splitlines() if "::" in line]
        if not collected:
            failures.append("phase B: collection reported no tests — a green "
                            "step that collected nothing proves nothing")
        else:
            print(f"[rehearsal] phase B: {len(collected)} core tests collect")

    if shutil.which("node"):
        rc, out = _run(["node", "scripts/guardrails-scan.mjs"], workspace, env)
        print(f"[rehearsal] phase B: guardrails scan -> exit {rc}")
        if rc != 0:
            failures.append("phase B: guardrails scan fails without the "
                            "boundary\n" + out.strip()[-2000:])
    else:
        print("[rehearsal] phase B: node absent — guardrails half skipped "
              "(stated, not silently passed)")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("."))
    parser.add_argument("--keep", action="store_true",
                        help="keep the workspaces and print their paths")
    args = parser.parse_args()
    source = args.source.resolve()
    if not (source / BOUNDARY_ROOT).is_dir():
        print(f"[rehearsal] no {BOUNDARY_ROOT}/ under {source}",
              file=sys.stderr)
        return 2
    declared = _manifest_paths(source)
    print(f"[rehearsal] source {source}; manifest declares "
          f"{len(declared)} path pattern(s)")

    failures = []
    root = Path(tempfile.mkdtemp(prefix="extraction-rehearsal-"))
    try:
        failures.extend(phase_a(source, root / "a"))
        failures.extend(phase_b(source, root / "b"))
    finally:
        if args.keep:
            print(f"[rehearsal] workspaces kept at {root}")
        else:
            shutil.rmtree(root, ignore_errors=True)

    if failures:
        print("[rehearsal] FAIL")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("[rehearsal] OK — boundary stands alone, core stands without it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
