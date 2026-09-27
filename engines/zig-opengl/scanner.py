"""Zig + OpenGL engine support for the DevGate game gates.

This module provides quality gates for Zig + OpenGL game projects.
Part of the in-tree game gates (merged 2026-09-26).

Modules:
- manifest.py: Read game-manifest.json for engine detection
- scanner.py: Discover .zig files, extract entity/handler definitions
- patterns.json: Zig-specific regression patterns (Z001-Z010)

Usage:
    python engines/zig-opengl/scanner.py --all
    python engines/zig-opengl/patterns.json
"""

import json
import re
from pathlib import Path


def detect_engine(root: Path) -> str:
    """Detect engine from game-manifest.json."""
    manifest_path = root / "game-manifest.json"
    if not manifest_path.exists():
        return "unknown"
    try:
        manifest = json.loads(manifest_path.read_text())
        return manifest.get("engine", "unknown")
    except (json.JSONDecodeError, OSError):
        return "unknown"


def is_zig_project(root: Path) -> bool:
    """Check if project uses Zig + OpenGL."""
    engine = detect_engine(root)
    return engine == "Zig + OpenGL"


def discover_zig_screens(root: Path) -> list[str]:
    """Find all .zig files under src/ — Zig project screens."""
    screens = []
    src = root / "src"
    if not src.is_dir():
        return screens
    for p in sorted(src.rglob("*.zig")):
        screens.append(str(p.relative_to(root)))
    return screens


def parse_zig_handlers(screen_path: str) -> tuple[list, list, list]:
    """Parse a .zig file for UI handler functions and entity definitions.

    Returns: (buttons, handlers, orphans)
    """
    text = Path(screen_path).read_text(errors="replace")

    buttons = []
    handlers = []

    # Find handler function definitions
    for m in re.finditer(r'(?:pub\s+)?fn\s+(\w+)\s*\(', text):
        handler_name = m.group(1)
        if handler_name not in ("init", "update", "render", "handle_input",
                                 "deinit", "show", "hide"):
            handlers.append(handler_name)

    # Find button definitions
    for m in re.finditer(r'\.label\s*=\s*"([^"]+)"', text):
        label = m.group(1)
        label_pos = m.start()
        nearby = text[label_pos:label_pos + 500]
        handler_match = re.search(r'\.handler\s*=\s*"([^"]+)"', nearby)
        if handler_match:
            buttons.append({"label": label, "handler": handler_match.group(1)})

    # Find orphaned handlers
    button_handlers = {b["handler"] for b in buttons}
    orphans = [h for h in handlers if h not in button_handlers]

    return buttons, handlers, orphans


def scan_project(root: Path) -> dict:
    """Scan entire Zig project and return validation results."""
    if not is_zig_project(root):
        return {"error": "Not a Zig project"}

    screens = discover_zig_screens(root)
    results = {
        "engine": "Zig + OpenGL",
        "screens_found": len(screens),
        "screens": [],
        "total_orphans": 0,
        "passed": True,
    }

    for screen in screens:
        buttons, handlers, orphans = parse_zig_handlers(str(root / screen))
        screen_result = {
            "path": screen,
            "buttons": len(buttons),
            "handlers": len(handlers),
            "orphans": len(orphans),
            "passed": len(orphans) == 0,
        }
        results["screens"].append(screen_result)
        results["total_orphans"] += len(orphans)
        if not screen_result["passed"]:
            results["passed"] = False

    return results
