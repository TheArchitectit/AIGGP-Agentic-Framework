"""Boundary validation on /enroll labels and /heartbeat fields (P0 hub)."""
import unittest, sys, importlib.util

class TestBoundaryValidation(unittest.TestCase):
    def test_labels_ok(self):
        from hub.server import _labels_ok
        self.assertTrue(_labels_ok(["a", "b"]))
        self.assertFalse(_labels_ok(["a" * 200]))   # too long
        self.assertFalse(_labels_ok("not a list"))
        self.assertFalse(_labels_ok(["x"] * 65))     # too many

    def test_scan_state_ok(self):
        from hub.server import _scan_state_ok
        self.assertTrue(_scan_state_ok({"repos": [{"name":"r","state":"clean"}]}))
        self.assertFalse(_scan_state_ok(None))  # not a dict; boundary rejects
        # Hostile payload: 300 repos or 100-char name
        bad = {"repos": [{"name":"x"*300, "state":"x"}]}
        self.assertFalse(_scan_state_ok(bad))
        self.assertFalse(_scan_state_ok("string"))

    def test_field_caps_defined(self):
        from hub.server import FIELD_CAPS
        self.assertIn("image_digest", FIELD_CAPS)
        self.assertLessEqual(FIELD_CAPS["image_digest"], 512)

if __name__ == "__main__":
    unittest.main()
