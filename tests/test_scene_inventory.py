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


def write_scene(root: Path, rel: str, content: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


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
