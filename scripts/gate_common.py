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
    load_source_dirs([devgate])     size-gate walk roots (candidates + overlay)
    load_size_overrides([devgate])  reasoned per-file hard/soft limit overrides
    read_jsonl_registry(path)       (entries, parse_errors)
    load_ignore_patterns(root)      .guardrailsignore
    is_ignored(file, root, pats)    relpath / basename / dir-prefix match
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
    worktrees        agent-created git worktree checkouts (2026-09-28)

Deliberately NOT in the list: ``pkg/`` — commonly first-party Go source.
The Go module cache lives outside the repo.

``load_source_dirs`` extends the size-gate walk the same way: a candidate
list (now including ``web`` / ``infra``) plus a scope.json
``extra_source_dirs`` overlay, so a consumer's new source root cannot silently
stay out of size scope (FAIL-f6228dda / FAIL-8f9249ca class — the 2026-10-11
gap where ``web/render3d.js`` at 1470 lines never reached the gate).
``load_size_overrides`` is the reasoned exception form (``reason`` required,
same contract as ``guardrails-allow``) — never a silent skip.

``line_has_allow`` requires reason text after the colon. That is the strictest
of the three historical matchers (guardrails-scan.mjs / semantic-scan.mjs /
regression_diff.py) and matches the documented annotation form
``guardrails-allow RULE-ID: <reason>``. A bare ``guardrails-allow ID:`` is not
an exemption.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
from project_root import project_root_for  # noqa: E402  # guardrails-allow PREVENT-024: shared root-contract module defined in scripts/lib/project_root.py, not an external package

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

    ``DEVGATE_PROJECT_ROOT`` overrides, matching what games, CI, and the
    fixture suites already use to point a scanner at a non-default tree.
    """
    env = os.environ.get("DEVGATE_PROJECT_ROOT")
    if env:
        return Path(env).resolve()
    return project_root_for(Path(devgate_root_) if devgate_root_ else devgate_root())


def _load_scope(devgate_root_: Path | str | None = None) -> tuple[dict, Path]:
    """Read the winning ``.guardrails/scope.json`` (project overlay first).

    Returns ``(data, path)``. Missing/invalid contract raises — a gate that
    silently scans the wrong tree is worse than one that refuses to run.
    """
    dg = Path(devgate_root_) if devgate_root_ else devgate_root()
    for candidate in (project_root(dg) / _SCOPE, dg / _SCOPE):
        if candidate.exists():
            data = json.loads(candidate.read_text(encoding="utf-8"))
            return data, candidate
    raise FileNotFoundError(
        "scope contract missing: .guardrails/scope.json (project root or .devgate/)"
    )


def load_skip_dirs(devgate_root_: Path | str | None = None) -> frozenset[str]:
    """Canonical SKIP_DIRS from ``.guardrails/scope.json`` (fw-scope-01).

    Project overlay wins over the submodule baseline so a consumer extends
    scope without editing DevGate. Missing/invalid contract raises — a gate
    that silently scans the wrong tree is worse than one that refuses to run.
    """
    data, path = _load_scope(devgate_root_)
    dirs = data.get("skip_dirs")
    if not isinstance(dirs, list):
        raise ValueError(f"{path}: skip_dirs must be a list")
    return frozenset(str(d) for d in dirs)


# Size-gate walk roots. Historical gap (2026-10-11): `web` and `infra` were
# absent, so web/render3d.js (1470) and web/index.html (685) sat past SRC_HARD
# while the walk never entered web/ — the FAIL-f6228dda shape again, one
# directory short. Frontend/infra roots are listed explicitly so a consumer
# does not have to know the contract to get sized.
DEFAULT_SOURCE_DIR_CANDIDATES: tuple[str, ...] = (
    "src", "lib", "app", "extensions", "scripts", "internal", "pkg", "cmd",
    "game", "router", "agents", "common", "tools", "migrations", "openspec",
    "hub", "go", "tests", "test",
    "web", "www", "public", "static", "client", "frontend", "backend", "server",
    "api", "infra", "components", "pages", "modules", "packages", "apps",
    "include", "bin", "examples", "utils", "services", "core", "shared",
)


def load_source_dirs(devgate_root_: Path | str | None = None) -> list[str]:
    """Source directories the size gate walks (fw-scope-01).

    Candidates that exist under the project root, then scope.json
    ``extra_source_dirs`` (overlay extension), then ``source_dirs`` (explicit
    replacement). Falls back to ``["."]`` when nothing matches. Submodule
    checkouts (a directory containing ``.git``) are never first-party scope.
    """
    data, _path = _load_scope(devgate_root_)
    root = project_root(devgate_root_)
    skip = {str(d) for d in data.get("skip_dirs", [])}

    explicit = data.get("source_dirs")
    if explicit is not None:
        if not isinstance(explicit, list):
            raise ValueError(f"{_path}: source_dirs must be a list")
        return [str(d) for d in explicit] or ["."]

    found: list[str] = []
    for candidate in DEFAULT_SOURCE_DIR_CANDIDATES:
        p = root / candidate
        if p.is_dir() and (p / ".git").exists() is False:
            found.append(candidate)

    extra = data.get("extra_source_dirs")
    if extra is not None:
        if not isinstance(extra, list):
            raise ValueError(f"{_path}: extra_source_dirs must be a list")
        for d in extra:
            name = str(d)
            if name not in found and name not in skip and (root / name).is_dir():
                found.append(name)

    return found or ["."]


def load_size_overrides(devgate_root_: Path | str | None = None) -> dict[str, dict]:
    """Per-file size-limit overrides from ``.guardrails/scope.json``.

    Shape: ``{"web/render3d.js": {"hard": 1600, "soft": 800, "reason": "..."}}``.
    ``reason`` is required and must be non-empty — the same contract as
    ``guardrails-allow`` (FAIL-9231181d). ``hard`` is required. Paths are
    posix repo-relative. Unknown keys are rejected so a typo cannot silently
    widen a limit.
    """
    data, path = _load_scope(devgate_root_)
    raw = data.get("size_overrides")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: size_overrides must be an object")
    allowed = {"hard", "soft", "reason"}
    out: dict[str, dict] = {}
    for rel, spec in raw.items():
        if not isinstance(spec, dict):
            raise ValueError(f"{path}: size_overrides[{rel!r}] must be an object")
        unknown = set(spec) - allowed
        if unknown:
            raise ValueError(f"{path}: size_overrides[{rel!r}] unknown keys {sorted(unknown)}")
        reason = spec.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"{path}: size_overrides[{rel!r}] requires a non-empty reason")
        hard = spec.get("hard")
        if not isinstance(hard, int) or hard <= 0:
            raise ValueError(f"{path}: size_overrides[{rel!r}] requires a positive int hard")
        entry = {"hard": hard, "reason": reason.strip()}
        if "soft" in spec:
            soft = spec["soft"]
            if not isinstance(soft, int) or soft < 0:
                raise ValueError(f"{path}: size_overrides[{rel!r}] soft must be a non-negative int")
            entry["soft"] = soft
        out[str(rel).replace("\\", "/")] = entry
    return out


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


def load_ignore_patterns(root: Path | str) -> list[str]:
    """Read ``<root>/.guardrailsignore`` — per-project scoping.

    One fnmatch glob per line (``*`` crosses ``/``, same as the rule globs);
    a trailing ``/`` marks a directory prefix. Blank lines and ``#`` comments
    ignored. Shared home for the loader game_regression and the Node scanners
    each carried.
    """
    path = Path(root) / ".guardrailsignore"
    if not path.exists():
        return []
    patterns: list[str] = []
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return patterns


def is_ignored(file_path: str, root: Path | str, patterns: list[str] | tuple[str, ...]) -> bool:
    """True when the file matches a ``.guardrailsignore`` entry.

    Matches the repo-relative path, the basename, or a directory prefix.
    """
    if not patterns:
        return False
    try:
        rel = os.path.relpath(str(file_path), str(root))
    except ValueError:
        rel = str(file_path)
    rel = rel.replace("\\", "/")
    base = os.path.basename(str(file_path))
    for pat in patterns:
        if pat.endswith("/"):
            if rel == pat[:-1] or rel.startswith(pat):
                return True
        elif fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(base, pat):
            return True
    return False


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


# First-party text file classification (fw-charset-01, fw-encoding-01,
# fw-corruption-01). One table so the charset, encoding-drift and
# corruption gates agree on what a "text file" is; a per-gate private list
# is the divergence class gate_common exists to prevent.
TEXT_EXTS: frozenset[str] = frozenset({
    ".md", ".markdown", ".txt", ".rst",
    ".py", ".go", ".rs", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".sh", ".bash", ".zsh", ".bat", ".cmd", ".ps1",
    ".yml", ".yaml", ".json", ".jsonl", ".toml", ".ini", ".cfg", ".env",
    ".sql", ".proto", ".html", ".css", ".hbs", ".xml", ".csv",
})
TEXT_BASENAMES: frozenset[str] = frozenset({
    ".gitignore", ".gitattributes", ".editorconfig", "dockerfile",
    "makefile", "license", "notice",
})


def is_text_file(path: str | Path) -> bool:
    """True when ``path`` is first-party text by extension or basename.

    Classification only; scope (SKIP_DIRS) is applied separately via
    ``load_skip_dirs``. Binary and vendored trees are never text.
    """
    p = Path(path)
    return p.suffix.lower() in TEXT_EXTS or p.name.lower() in TEXT_BASENAMES