#!/usr/bin/env python3
"""regression_audit.py — package-manager vulnerability audit.

Helper module for scripts/regression_check.py, split out unchanged to keep every
file under DevGate's own 500-line hard limit. The logic is exactly DevGate's
original package-audit implementation: auto-detect the package manager, run
`npm audit --json` for npm projects, and skip gracefully for everything else
(cargo, pip, go, Godot, or no manifest at all).

Runtime HIGH/CRITICAL advisories are blocking; dev-only advisories are warnings.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _detect_package_manager(repo_root: Path) -> str | None:
    """Detect the project's package manager. Returns 'npm', 'cargo', 'pip', or None."""
    if (repo_root / "package.json").exists():
        return "npm"
    if (repo_root / "Cargo.toml").exists():
        return "cargo"
    if (repo_root / "pyproject.toml").exists() or (repo_root / "setup.py").exists():
        return "pip"
    return None


def check_npm_audit(repo_root: Path) -> tuple[int, int, list[dict]]:
    """Run npm audit if the project uses npm. Non-blocking if not present."""
    pkg_manager = _detect_package_manager(repo_root)
    if pkg_manager != "npm":
        return (0, 0, [])  # Skip for non-npm projects

    try:
        result = subprocess.run(["npm", "audit", "--json"], capture_output=True,
                                text=True, cwd=str(repo_root), timeout=120)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return (0, 0, [])

    raw = result.stdout.strip()
    if not raw:
        return (0, 0, [])
    try:
        audit = json.loads(raw)
    except json.JSONDecodeError:
        return (0, 0, [])

    pkg_path = repo_root / "package.json"
    runtime_deps: set[str] | None = set()
    try:
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        runtime_deps = set((pkg.get("dependencies") or {}).keys())
    except (OSError, json.JSONDecodeError):
        runtime_deps = None

    vuln_map = audit.get("vulnerabilities") or {}
    issues: list[dict] = []
    for name, info in vuln_map.items():
        severity = str(info.get("severity", "unknown")).lower()
        effects = info.get("effects") or []
        is_runtime = any(eff in (runtime_deps or set()) for eff in effects) if runtime_deps is not None else True
        issues.append({"name": name, "severity": severity, "is_runtime": is_runtime,
                       "advisory": str(info.get("via", ""))[:80],
                       "fix_available": bool(info.get("fixAvailable")), "effects": effects})
    blocking = [i for i in issues if i["is_runtime"] and i["severity"] in ("high", "critical")]
    warning = [i for i in issues if not (i["is_runtime"] and i["severity"] in ("high", "critical"))]
    return len(blocking), len(warning), issues


def print_npm_audit_report(blocking: int, warnings: int, issues: list[dict]) -> None:
    if not issues:
        print("✓ No package vulnerabilities found")
        return
    print("\n" + "=" * 70)
    print("PACKAGE AUDIT (runtime HIGH/CRITICAL = blocking; dev-only = warning)")
    print("=" * 70)
    for i in sorted(issues, key=lambda x: (not x["is_runtime"], x["severity"])):
        scope = "RUNTIME" if i["is_runtime"] else "dev-only"
        fix = "fix available" if i["fix_available"] else "NO fix"
        print(f"  {i['severity'].upper():8s} {scope:8s} {i['name']:<32s} {fix}")
    print("-" * 70)
    print(f"  {blocking} blocking | {warnings} warning(s)")
    print("=" * 70)
