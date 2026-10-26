"""Behavioral self-test for scripts/scene_inventory.py (QA C1).

The gate used to call xml.etree.ElementTree.parse on .tscn files — which are
Godot's TEXT scene format, not XML — so every valid scene reported
"parse error" and the gate could not pass on ANY real input. These tests feed
the parser real minimal .tscn content: a connected button must pass, an
orphaned button must fail, a nested node path must not false-positive, and an
empty scope must read as NOTHING SCANNED rather than a clean pass.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import scene_inventory as si  # noqa: E402

VALID_SCENE = """[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/hud.gd" id="1"]

[node name="HUD" type="Control"]

[node name="Panel" type="PanelContainer" parent="."]

[node name="PlayButton" type="Button" parent="Panel"]
text = "Play"

[connection signal="pressed" from="Panel/PlayButton" to="." method="_on_play_pressed"]
"""

ORPHAN_SCENE = """[gd_scene format=3]

[node name="Menu" type="Control"]

[node name="QuitButton" type="Button" parent="."]
text = "Quit"
"""

# The same scene as ORPHAN_SCENE, plus the script it runs — no [connection]
# block, because the handler is wired in _ready(). This is what Godot's editor
# and its own docs produce, and what MergeKingdom's popups do.
CODE_WIRED_SCENE = """[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://src/ui/Menu.gd" id="1"]

[node name="Menu" type="Control"]
script = ExtResource("1")

[node name="Panel" type="PanelContainer" parent="."]

[node name="QuitButton" type="Button" parent="Panel"]
text = "Quit"
"""

DIRECT_WIRING_SCRIPT = """extends Control

func _ready() -> void:
\t$Panel/QuitButton.pressed.connect(_on_quit)

func _on_quit() -> void:
\tget_tree().quit()
"""

ONREADY_WIRING_SCRIPT = """extends Control

@onready var quit_btn: Button = $Panel/QuitButton

func _ready() -> void:
\tquit_btn.pressed.connect(_on_quit)

func _on_quit() -> void:
\tget_tree().quit()
"""

# Wires a DIFFERENT button, so the scene's own button must stay an orphan.
OTHER_BUTTON_SCRIPT = """extends Control

func _ready() -> void:
\t$Panel/SomethingElse.pressed.connect(_on_other)
"""

COMMENTED_OUT_SCRIPT = """extends Control

func _ready() -> void:
\t# $Panel/QuitButton.pressed.connect(_on_quit)
\tpass
"""


def write_scene(root: Path, rel: str, content: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def write_tree(root: Path, script_src: str) -> None:
    """A scene plus the script it runs, mirroring a real Godot layout."""
    write_scene(root, "src/ui/Menu.tscn", CODE_WIRED_SCENE)
    write_scene(root, "src/ui/Menu.gd", script_src)


class TestTscnParsing(unittest.TestCase):
    def test_valid_scene_parses_and_connected_button_is_not_orphaned(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_scene(root, "src/UI/HUD.tscn", VALID_SCENE)
            buttons, connections, orphaned = si.parse_tscn_buttons(
                root / "src/UI/HUD.tscn")
        self.assertEqual(buttons, ["PlayButton"])
        self.assertEqual(len(connections), 1)
        self.assertEqual(orphaned, [],
                         "node-path connection must match the bare button name")

    def test_orphaned_button_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_scene(root, "src/UI/Menu.tscn", ORPHAN_SCENE)
            buttons, _, orphaned = si.parse_tscn_buttons(root / "src/UI/Menu.tscn")
        self.assertEqual(buttons, ["QuitButton"])
        self.assertEqual(orphaned, ["QuitButton"])

    def test_scan_project_passes_valid_scene(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_scene(root, "src/UI/HUD.tscn", VALID_SCENE)
            rc = si.scan_project(root)
        self.assertEqual(rc, 0, "a valid scene must PASS — QA C1 regression")

    def test_scan_project_fails_orphaned_scene(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_scene(root, "src/UI/Menu.tscn", ORPHAN_SCENE)
            rc = si.scan_project(root)
        self.assertEqual(rc, 1)

    def test_scenes_outside_src_are_discovered(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_scene(root, "scenes/Main.tscn", ORPHAN_SCENE)
            scenes = si.discover_scenes_godot(root)
        self.assertIn("scenes/Main.tscn", scenes,
                      "standard res://scenes layout must not be invisible")


class TestCodeSideWiring(unittest.TestCase):
    """A button wired from the scene's script is connected — the gate used to
    read .tscn connection blocks only, so every code-wired Godot UI read as
    orphaned (MergeKingdom 2026-10-25: 4 scenes / 8 buttons, all correctly
    wired). These tests pin both directions: code wiring clears the orphan, and
    a script that wires something else does not.
    """

    def test_resolve_scene_script_finds_the_root_scripts_resource(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_tree(root, DIRECT_WIRING_SCRIPT)
            script = si.resolve_scene_script(root / "src/ui/Menu.tscn", root)
        self.assertEqual(script.name, "Menu.gd")

    def test_direct_dollar_path_wiring_is_not_orphaned(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_tree(root, DIRECT_WIRING_SCRIPT)
            self.assertEqual(si.scan_project(root), 0)

    def test_onready_variable_wiring_is_not_orphaned(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_tree(root, ONREADY_WIRING_SCRIPT)
            self.assertEqual(si.scan_project(root), 0)

    def test_script_that_wires_another_button_leaves_the_orphan(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_tree(root, OTHER_BUTTON_SCRIPT)
            self.assertEqual(si.scan_project(root), 1,
                             "wiring a different node must not clear the orphan")

    def test_commented_out_wiring_still_reads_as_orphaned(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_tree(root, COMMENTED_OUT_SCRIPT)
            self.assertEqual(si.scan_project(root), 1,
                             "a commented-out connect() is not a handler")

    def test_scene_with_no_script_keeps_its_orphan(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_scene(root, "src/ui/Menu.tscn", ORPHAN_SCENE)
            self.assertEqual(si.scan_project(root), 1)

    def test_wired_paths_are_reported_as_a_set(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_tree(root, ONREADY_WIRING_SCRIPT)
            wired = si.parse_script_wiring(root / "src/ui/Menu.gd")
        self.assertEqual(wired, {"Panel/QuitButton"})


class TestNoVacuousGreen(unittest.TestCase):
    def test_empty_scope_is_nothing_scanned_not_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            import io
            import contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = si.scan_project(root)
            out = buf.getvalue()
        self.assertEqual(rc, 0, "default stays non-blocking for non-Godot repos")
        self.assertIn("NOTHING SCANNED", out,
                      "zero scenes must not read as a clean pass")

    def test_fail_if_empty_exits_2(self):
        with tempfile.TemporaryDirectory() as td:
            rc = si.scan_project(Path(td), fail_if_empty=True)
        self.assertEqual(rc, 2)

    def test_cli_fail_if_empty_flag(self):
        with tempfile.TemporaryDirectory() as td:
            r = subprocess.run(
                [sys.executable,
                 str(Path(__file__).resolve().parent.parent /
                     "scripts/scene_inventory.py"),
                 "--root", td, "--fail-if-empty"],
                capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("NOTHING SCANNED", r.stdout)


if __name__ == "__main__":
    unittest.main()
