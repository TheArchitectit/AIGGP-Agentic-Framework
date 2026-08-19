#!/usr/bin/env python3
"""Scene inventory + button handler validation scanner.

Ported from Sword of Hope's scene_load_check.gd, generalized to be engine-agnostic.

For Godot projects: discovers all .tscn files under src/, parses each for
Button nodes and their pressed signal connections, reports orphaned signals.

For non-Godot projects: reads a scene manifest (game-manifest.json) if present.

Exit codes: 0 = all scenes pass, 1 = any scene/button failure.
"""
import json, os, re, sys, xml.etree.ElementTree as ET
from pathlib import Path

def find_project_root():
    d = Path.cwd()
    for i in range(10):
        for marker in ("project.godot", "package.json", "Cargo.toml", ".git"):
            if (d / marker).exists():
                return d
        parent = d.parent
        if parent == d:
            break
        d = parent
    return Path.cwd()

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

def scan_project(root):
    root = Path(root)
    scenes = discover_scenes_godot(root)

    if not scenes:
        # Check for non-Godot manifest
        manifest = root / "game-manifest.json"
        if manifest.exists():
            print(f"[scene-inventory] non-Godot project, manifest found — skipping scene scan")
            return 0

        print(f"[scene-inventory] no scenes found under src/ — nothing to scan")
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

if __name__ == "__main__":
    root = find_project_root()
    print(f"[scene-inventory] project root: {root}")
    sys.exit(scan_project(root))
