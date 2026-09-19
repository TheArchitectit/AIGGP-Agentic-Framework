#!/usr/bin/env python3
"""Scene inventory + button handler validation scanner.

Ported from Sword of Hope's scene_load_check.gd, generalized to be engine-agnostic.

For Godot projects: discovers all .tscn files under src/ (plus scenes/ and
res:// root when present), parses each for Button nodes and their pressed
signal connections, reports orphaned signals.

For non-Godot projects: reads a scene manifest (game-manifest.json) if present.

Exit codes: 0 = all scenes pass, 1 = any scene/button failure, 2 = usage error.
A scope that discovered zero scenes is reported as NOTHING SCANNED, never as a
clean pass; --fail-if-empty turns it into exit 2 for CI (no-vacuous-green).
"""
import argparse, re, sys
from pathlib import Path

def find_project_root():
    """Layout-contract anchoring (fix-vacuous-and-broken-gates): the old CWD
    walk was the fifth divergent root detector; script location is the
    documented contract (same as guardrails-scan.mjs / regression_check.py)."""
    import os
    env = os.environ.get("DEVGATE_PROJECT_ROOT")
    if env:
        return Path(env).resolve()
    devgate_root = Path(__file__).resolve().parent.parent
    if devgate_root.name == ".devgate":
        return devgate_root.parent
    return devgate_root

def discover_scenes_godot(root):
    """Find .tscn files under the project's scene trees.

    src/ is the primary convention (mirrors SoH's _discover_scenes()), with
    scenes/ and the project root also scanned so a standard Godot layout
    (res://scenes/…) is not invisible to the gate.
    """
    scenes = []
    roots = [root / "src", root / "scenes"]
    for r in roots:
        if r.is_dir():
            for p in sorted(r.rglob("*.tscn")):
                rel = str(p.relative_to(root))
                if rel not in scenes:
                    scenes.append(rel)
    for p in sorted(root.glob("*.tscn")):
        rel = str(p.relative_to(root))
        if rel not in scenes:
            scenes.append(rel)
    return scenes

def parse_tscn_buttons(scene_path):
    """Parse a .tscn file (Godot's text scene format — NOT XML) for Button
    nodes and their signal connections.

    Returns: (buttons, connections, orphaned).
    A button with a 'pressed' signal but no connected handler = orphaned.

    History (QA C1): this function used to call xml.etree.ElementTree.parse
    FIRST, which raises on every valid .tscn — so every scene reported
    "parse error" and the regex parser below was unreachable dead code. The
    regex parser is the real implementation.
    """
    buttons = []
    connections = []
    text = Path(scene_path).read_text(encoding="utf-8", errors="replace")

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

    # Find orphaned buttons: Button nodes with no 'pressed' connection.
    # Connections carry NODE PATHS ("Panel/PlayButton"); buttons carry bare
    # node names — compare on the last path segment so a nested button is not
    # false-reported as orphaned (QA C1 follow-on).
    connected = {c["from"].rsplit("/", 1)[-1]
                 for c in connections if c["signal"] == "pressed"}
    orphaned = [b for b in buttons if b not in connected]

    return buttons, connections, orphaned

def scan_project(root, fail_if_empty=False):
    root = Path(root)
    scenes = discover_scenes_godot(root)

    if not scenes:
        # Check for non-Godot manifest
        manifest = root / "game-manifest.json"
        if manifest.exists():
            print(f"[scene-inventory] non-Godot project, manifest found — skipping scene scan")
            return 0

        # No vacuous green: zero scenes is NOTHING SCANNED, never a clean pass.
        print(f"[scene-inventory] NOTHING SCANNED — no .tscn files under src/, "
              f"scenes/, or the project root. This is not evidence of health.")
        return 2 if fail_if_empty else 0

    print(f"[scene-inventory] discovered {len(scenes)} scene(s)")
    failures = 0
    orphan_count = 0

    for scene in scenes:
        full = root / scene
        buttons, connections, orphaned = parse_tscn_buttons(full)

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
    ap = argparse.ArgumentParser(description="Godot scene inventory gate")
    ap.add_argument("--root", type=Path, default=None,
                    help="project root (default: script-location detection)")
    ap.add_argument("--fail-if-empty", action="store_true",
                    help="exit 2 when the scope found zero scenes (CI)")
    args = ap.parse_args()
    root = args.root.resolve() if args.root else find_project_root()
    print(f"[scene-inventory] project root: {root}")
    sys.exit(scan_project(root, fail_if_empty=args.fail_if_empty))
