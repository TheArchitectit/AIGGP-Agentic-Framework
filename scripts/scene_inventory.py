#!/usr/bin/env python3
"""Scene inventory + button handler validation scanner.

Engine-aware: detects the project engine (game-manifest.json, else project
files) and dispatches to the matching scanner.

  Godot        — discovers .tscn files under src/, parses Button nodes and their
                 'pressed' signal connections, reports orphaned signals.
  Zig + OpenGL — discovers .zig UI screens under src/ui/, validates handler
                 bindings declared alongside .label buttons.

Ported from Sword of Hope's scene_load_check.gd, generalized to be
engine-agnostic. Zig + OpenGL support imported from the former
devgate-game-framework repository (merged 2026-09-26).

Exit codes: 0 = all scenes pass, 1 = any scene/button failure.
"""
import json, os, re, sys, xml.etree.ElementTree as ET
from pathlib import Path

# Project root by LAYOUT CONTRACT — the same shared rule as regression_check.py
# and the Node scanners (root-anchor-01/-03). The old find_project_root() walked
# up from Path.cwd() for a marker, so it both escaped to a sibling directory
# above the checkout and changed answer with the invocation cwd. scripts/ lives
# directly under the DevGate root, so parent.parent is that root.
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from project_root import project_root_for  # noqa: E402  # guardrails-allow PREVENT-024: shared root-contract module defined in scripts/lib/project_root.py, not an external package

PROJECT_ROOT = project_root_for(Path(__file__).resolve().parent.parent)

def detect_engine(root):
    """Detect the project engine from game-manifest.json, else project files.

    Manifest `engine` wins; otherwise project/build markers are consulted. Kept
    in parity with game_regression.detect_engine so both game gates agree.
    """
    root = Path(root)
    manifest_path = root / "game-manifest.json"
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text()).get("engine", "unknown")
        except Exception:
            pass
    if (root / "project.godot").exists():
        return "Godot"
    if (root / "build.zig").exists():
        return "Zig + OpenGL"
    return "unknown"

# === GODOT SCANNER ===

def discover_scenes_godot(root):
    """Find all .tscn files under src/ — mirrors SoH's _discover_scenes()."""
    scenes = []
    src = root / "src"
    if not src.is_dir():
        return scenes
    for p in sorted(src.rglob("*.tscn")):
        scenes.append(str(p.relative_to(root)))
    return scenes

def parse_tscn_buttons(scene_path):
    """Parse a .tscn file for Button nodes and their signal connections.

    Returns: list of {node, signal, target, method} dicts.
    A button with a 'pressed' signal but no connected handler = orphaned.
    """
    try:
        tree = ET.parse(scene_path)
    except Exception:
        return [], "parse error"

    buttons = []
    connections = []
    # .tscn is not real XML but has ExtResource/InternalResource blocks
    # Parse with regex instead
    text = Path(scene_path).read_text(errors="replace")

    # Find Button nodes
    for m in re.finditer(r'\[node\s+name="([^"]+)"[^]]*type="Button"', text):
        buttons.append(m.group(1))

    # Find signal connections: [connection signal="pressed" from="NodeName" to="TargetName" method="method_name"]
    for m in re.finditer(r'\[connection\s+signal="([^"]+)"\s+from="([^"]+)"\s+to="([^"]+)"\s+method="([^"]+)"', text):
        connections.append({
            "signal": m.group(1),
            "from": m.group(2),
            "to": m.group(3),
            "method": m.group(4),
        })

    # Find orphaned buttons: Button nodes with no 'pressed' connection
    connected = {c["from"] for c in connections if c["signal"] == "pressed"}
    orphaned = [b for b in buttons if b not in connected]

    return buttons, connections, orphaned

def scan_godot(root):
    root = Path(root)
    scenes = discover_scenes_godot(root)

    if not scenes:
        print(f"[scene-inventory] no .tscn scenes found under src/ — nothing to scan")
        return 0

    print(f"[scene-inventory] discovered {len(scenes)} scene(s) under src/")
    failures = 0
    orphan_count = 0

    for scene in scenes:
        full = root / scene
        result = parse_tscn_buttons(full)

        if isinstance(result, tuple) and len(result) == 3:
            buttons, connections, orphaned = result
        else:
            print(f"  FAIL {scene}: parse error")
            failures += 1
            continue

        status = "OK"
        if orphaned:
            status = f"ORPHANED: {len(orphaned)} button(s) without 'pressed' handler"
            orphan_count += len(orphaned)
            failures += 1

        button_count = len(buttons)
        conn_count = len(connections)
        print(f"  {'FAIL' if orphaned else 'OK'} {scene} — {button_count} button(s), {conn_count} connection(s){' — ' + status if orphaned else ''}")

        for o in orphaned:
            print(f"    ORPHAN: Button '{o}' has no 'pressed' signal connection")

    print()
    print(f"=== Scene Inventory Summary ===")
    print(f"Scenes: {len(scenes)}, Failures: {failures}, Orphaned buttons: {orphan_count}")
    return 1 if failures > 0 else 0

# === ZIG + OPENGL SCANNER ===

def load_non_screen_files(root):
    """Read `scan.non_screen_files` from game-manifest.json.

    The scanner's premise is that every `.zig` under `src/ui/` is a screen. That
    holds for screens and fails for a *container* — a file that owns the screen
    instances and the dispatch switch, whose methods are legitimately not
    button-connected. Reported as orphans, such a file fails the gate for being
    infrastructure rather than a screen.

    A project cannot fix this from its side without deforming its layout, so it
    declares the exception instead. Paths are project-root-relative.
    """
    manifest_path = root / "game-manifest.json"
    if not manifest_path.exists():
        return set()
    try:
        manifest = json.loads(manifest_path.read_text())
    except Exception:
        return set()
    scan = manifest.get("scan") or {}
    return {str(f).replace("\\", "/") for f in (scan.get("non_screen_files") or [])}

def discover_zig_screens(root):
    """Find .zig files under src/ui/ — Zig project UI screens."""
    screens = []
    ui_dir = root / "src" / "ui"
    if not ui_dir.is_dir():
        return screens
    non_screen = load_non_screen_files(root)
    for p in sorted(ui_dir.rglob("*.zig")):
        rel = str(p.relative_to(root)).replace("\\", "/")
        if rel in non_screen:
            continue
        screens.append(str(p.relative_to(root)))
    return screens

def parse_zig_handlers(screen_path):
    """Parse a .zig file for UI handler functions and entity definitions."""
    text = Path(screen_path).read_text(errors="replace")

    buttons = []
    for m in re.finditer(r'\.label\s*=\s*"([^"]+)"', text):
        label = m.group(1)
        label_pos = m.start()
        nearby = text[label_pos:label_pos + 500]
        handler_match = re.search(r'\.handler\s*=\s*"([^"]+)"', nearby)
        if handler_match:
            buttons.append({"label": label, "handler": handler_match.group(1)})

    internal_fns = {
        "init", "update", "render", "handle_input", "deinit",
        "show", "hide", "updateHUD", "checkWarnings", "showAnimation",
        "initScreen", "showScreen", "hideScreen",
    }
    handlers = []
    for m in re.finditer(r'(?:pub\s+)?fn\s+(\w+)\s*\(', text):
        fn = m.group(1)
        if fn not in internal_fns:
            handlers.append(fn)

    button_handlers = {b["handler"] for b in buttons}
    orphans = [h for h in handlers if h not in button_handlers]
    return buttons, handlers, orphans

def scan_zig(root):
    screens = discover_zig_screens(root)
    if not screens:
        print("[scene-inventory] no Zig UI screens found under src/ui/")
        return 0

    print(f"[scene-inventory] discovered {len(screens)} Zig screen(s) under src/ui/")
    failures = 0
    orphan_count = 0

    for screen in screens:
        full = root / screen
        buttons, handlers, orphans = parse_zig_handlers(str(full))

        if not buttons and not handlers:
            print(f"  SKIP {screen} — no UI definitions found")
            continue

        status = "OK"
        if orphans:
            status = f"ORPHANED: {len(orphans)} handler(s) without button connection"
            orphan_count += len(orphans)
            failures += 1

        print(f"  {'FAIL' if orphans else 'OK'} {screen} — {len(buttons)} button(s), {len(handlers)} handler(s){' — ' + status if orphans else ''}")
        for o in orphans:
            print(f"    ORPHAN: Handler '{o}' has no connected button/entity")

    print(f"\n=== Scene Inventory Summary ===")
    print(f"Screens: {len(screens)}, Failures: {failures}, Orphaned handlers: {orphan_count}")
    return 1 if failures > 0 else 0

# === MAIN DISPATCH ===

def scan_project(root):
    root = Path(root)
    engine = detect_engine(root)
    print(f"[scene-inventory] detected engine: {engine}")

    if engine == "Zig + OpenGL":
        return scan_zig(root)
    if engine == "Godot":
        return scan_godot(root)
    # Fall back to markers when the manifest is absent or names an unknown engine.
    if (root / "project.godot").exists():
        return scan_godot(root)
    if (root / "build.zig").exists():
        return scan_zig(root)
    print(f"[scene-inventory] unknown engine — no scenes to scan")
    return 0

if __name__ == "__main__":
    print(f"[scene-inventory] project root: {PROJECT_ROOT}")
    sys.exit(scan_project(PROJECT_ROOT))
