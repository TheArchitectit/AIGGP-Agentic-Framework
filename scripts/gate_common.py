#!/usr/bin/env python3
# // spec: fw-scope-01
"""gate_common.py — one home for the primitives every gate needs.

This exists because the 2026-09-19 scripts review found the same logic
implemented N times with N divergent behaviors. Root detection, SKIP_DIRS,
glob matching, allow-annotation parsing, and JSONL registry loading all
picked a different contract per file, which meant a fix ported poorly (the
guardrails-scan root fix never reached the other two scanners) and the parity
claims in comments were unverifiable.

Public surface (stdlib-only; safe to `import gate_common` after putting
``scripts/`` on sys.path):

    devgate_root()                  the .devgate/ or standalone checkout
    project_root([devgate])         layout-contract project root
    load_skip_dirs([devgate])       canonical SKIP_DIRS from .guardrails/scope.json
    read_jsonl_registry(path)       (entries, parse_errors)
    line_has_allow(line, *ids)      guardrails-allow <ID>: <reason>
    glob_matches(path, globs)       basename OR relpath, with ** globstar
    nothing_scanned(gate, reason)   vacuous-scan report (never a green pass)
    detect_package_manager(root)    npm | cargo | pip | go | godot | None

Module layout: primitives live here; the one already-correct root contract
stays in scripts/lib/project_root.py (root-anchor-01/-03) and is re-exported
by ``project_root_for``. Overlay merge stays in gate_overlay.py (it already
owns the submodule + overlay resolution) — this module does not reimplement it.

SKIP_DIRS per-name rationale (fw-scope-01, single source .guardrails/scope.json).
Loaded, never redeclared. Names:

    .claude          agent tool state
    .crew            agent scratch
    .devgate         the submodule itself (never first-party project source)
    .git             VCS metadata
    .next .nuxt   framework build output
    .sandbox-home    layers sandbox state (the reported vendored-divergence case)
    .venv venv       Python virtualenvs
    __pycache__      Python bytecode
    build dist out target   build/output trees
    egg-info         Python packaging metadata
    node_modules     JS dependency tree
    vendor           third-party pinned source

Deliberately NOT in the list: ``pkg/`` — commonly first-party Go source.
The Go module cache lives outside the repo.

``line_has_allow`` requires reason text after the colon. That is the strictest
of the three historical matchers (guardrails-scan.mjs / semantic-scan.mjs /
regression_diff.py) and matches the documented annotation form
``guardrails-allow RULE-ID: <reason>``. A bare ``guardrails-allow ID:`` is not
an exemption.
"""
from __future__ import annotations

import fnmatch
import json
import re
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
from project_root import project_root_for  # noqa: E402  (scripts/lib, set up above)

_SCOPE = Path(".guardrails") / "scope.json"

# Canonical package-manager detection (QA C6-adjacent; deploy.sh and
# regression_audit.py share this table). go/godot were the gap — deploy.sh
# knew them, the audit side did not.
_PACKAGE_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("npm", ("package.json",)),
    ("cargo", ("Cargo.toml",)),
    ("pip", ("pyproject.toml", "setup.py")),
    ("go", ("go.mod",)),
    ("godot", ("project.godot",)),
)


def devgate_root() -> Path:
    """The DevGate checkout that contains this ``scripts/`` folder."""
    return Path(__file__).resolve().parent.parent


def project_root(devgate_root_: Path | str | None = None) -> Path:
    """Layout-contract project root — never a marker walk-up.

    Submodule layout (``<project>/.devgate/``) → the project. Standalone
    checkout → DevGate itself. See ``project_root_for`` / root-anchor-01.
    """
    return project_root_for(Path(devgate_root_) if devgate_root_ else devgate_root())


def load_skip_dirs(devgate_root_: Path | str | None = None) -> frozenset[str]:
    """Canonical SKIP_DIRS from ``.guardrails/scope.json`` (fw-scope-01).

    Project overlay wins over the submodule baseline so a consumer extends
    scope without editing DevGate. Missing/invalid contract raises — a gate
    that silently scans the wrong tree is worse than one that refuses to run.
    """
    dg = Path(devgate_root_) if devgate_root_ else devgate_root()
    for candidate in (project_root(dg) / _SCOPE, dg / _SCOPE):
        if candidate.exists():
            data = json.loads(candidate.read_text(encoding="utf-8"))
            dirs = data.get("skip_dirs")
            if not isinstance(dirs, list):
                raise ValueError(f"{candidate}: skip_dirs must be a list")
            return frozenset(str(d) for d in dirs)
    raise FileNotFoundError(
        "scope contract missing: .guardrails/scope.json (project root or .devgate/)"
    )


def read_jsonl_registry(path: Path | str) -> tuple[list[dict], list[str]]:
    """Parse a JSONL registry: blank lines and ``#`` comments skipped.

    Returns ``(entries, parse_errors)``. Per-line JSON failures are reported
    in ``parse_errors`` (failure_registry_check semantics, not gate_overlay's
    silent skip) — a corrupted line is a defect, not a null entry to drop.
    A missing file is one error, not an empty success.
    """
    path = Path(path)
    entries: list[dict] = []
    errors: list[str] = []
    if not path.exists():
        errors.append(f"registry not found: {path}")
        return entries, errors
    if path.is_dir():
        errors.append(f"registry path is a directory: {path}")
        return entries, errors
    with open(path, encoding="utf-8", errors="replace") as fh:
        for lineno, raw in enumerate(fh, 1):
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                entries.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                errors.append(f"line {lineno}: JSON parse error — {exc}")
    return entries, errors


def line_has_allow(line: str, *ids: str) -> bool:
    """True when the line carries ``guardrails-allow <ID>: <reason>``.

    Keys on the rule/failure id so one id's allow cannot silence another
    pattern. Reason text is required (``:\\s*\\S``) — a trailing colon with no
    justification is not an exemption. Identical semantics intended for
    every scanner (FAIL-9231181d).
    """
    return any(
        re.search(rf"guardrails-allow\s+{re.escape(i)}\s*:\s*\S", line)
        for i in ids
        if i
    )


def _expand_globstars(globs: list[str] | tuple[str, ...]) -> list[str]:
    """Yield each glob plus the stripped-** variants fnmatch needs."""
    out: list[str] = []
    for g in globs:
        out.append(g)
        if g.endswith("/**"):
            out.append(g[:-3] + "*")
        if "/**/" in g:
            out.append(g.replace("/**/", "/", 1))
        if g.endswith("/**"):
            stripped = g[:-3]
            if "/**/" in stripped:
                out.append(stripped.replace("/**/", "/", 1))
    return out


def glob_matches(path: str, globs: list[str] | tuple[str, ...] | None) -> bool:
    """True when the basename OR the repo-relative path matches any glob.

    ``**`` is expanded for fnmatch compatibility (``a/**/b`` matches ``a/b``);
    ``src/**/*`` also matches the zero-directory form (``src/a.rs``). Python
    fnmatch's ``*`` already crosses ``/``, which is the same contract
    guardrails-scan.mjs implements with its own translator.
    """
    if not globs:
        return False
    base = path.rsplit("/", 1)[-1]
    for g in _expand_globstars(list(globs)):
        if fnmatch.fnmatch(base, g) or fnmatch.fnmatch(path, g):
            return True
        if g.endswith("/**/*") and (path == g[:-5] or path.startswith(g[:-4])):
            return True
    return False


def nothing_scanned(gate: str, reason: str, *, fail_if_empty: bool = False) -> int:
    """Report a scope that evaluated zero targets.

    Prints ``NOTHING SCANNED`` (the shared non-vacuity marker) and returns the
    exit code: 0 by default (non-CI / advisory), 2 when ``fail_if_empty``
    (CI). Never a bare pass — an empty scope is not a green result.
    """
    print(f"[{gate}] NOTHING SCANNED — {reason}")
    return 2 if fail_if_empty else 0


def detect_package_manager(repo_root: Path | str) -> str | None:
    """Return the package manager of ``repo_root``, or None.

    One table (npm, cargo, pip, go, godot) for deploy.sh and
    regression_audit.py. First marker wins.
    """
    root = Path(repo_root)
    for name, markers in _PACKAGE_MARKERS:
        if any((root / m).exists() for m in markers):
            return name
    return None