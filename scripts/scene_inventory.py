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

Exit codes: 0 = all scenes pass, 1 = any scene/button failure, 2 = usage error.
A scope that discovered zero scenes is reported as NOTHING SCANNED, never as a
clean pass; --fail-if-empty turns it into exit 2 for CI (no-vacuous-green).
"""
import argparse, json, re, sys
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
    # A tree whose only engine signal is the scenes themselves is still Godot —
    # otherwise a project with just .tscn files is invisible to the scan.
    try:
        next(root.rglob("*.tscn"))
        return "Godot"
    except StopIteration:
        pass
    return "unknown"

# === GODOT SCANNER ===

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

def scan_godot(root, fail_if_empty=False):
    root = Path(root)
    scenes = discover_scenes_godot(root)

    if not scenes:
        print("[scene-inventory] NOTHING SCANNED — no .tscn scenes found under src/")
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

def scan_zig(root, fail_if_empty=False):
    screens = discover_zig_screens(root)
    if not screens:
        print("[scene-inventory] NOTHING SCANNED — no Zig UI screens found under src/ui/")
        return 2 if fail_if_empty else 0

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

def scan_project(root, fail_if_empty=False):
    root = Path(root)
    engine = detect_engine(root)
    print(f"[scene-inventory] detected engine: {engine}")

    if engine == "Zig + OpenGL":
        return scan_zig(root, fail_if_empty=fail_if_empty)
    if engine == "Godot":
        return scan_godot(root, fail_if_empty=fail_if_empty)
    # Fall back to markers when the manifest is absent or names an unknown engine.
    if (root / "project.godot").exists():
        return scan_godot(root, fail_if_empty=fail_if_empty)
    if (root / "build.zig").exists():
        return scan_zig(root, fail_if_empty=fail_if_empty)
    print("[scene-inventory] NOTHING SCANNED — unknown engine, no scenes to scan")
    return 2 if fail_if_empty else 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Scene inventory + button handler validation")
    ap.add_argument("--root", default=None,
                    help="project root (default: layout-contract PROJECT_ROOT)")
    ap.add_argument("--fail-if-empty", action="store_true",
                    help="turn a zero-scene scope into exit 2 (no-vacuous-green)")
    args = ap.parse_args()
    root = Path(args.root) if args.root else PROJECT_ROOT
    print(f"[scene-inventory] project root: {root}")
    sys.exit(scan_project(root, fail_if_empty=args.fail_if_empty))
