"""Smoke: server imports cleanly with new exceptions and validators."""
import unittest

class TestServerSmoke(unittest.TestCase):
    def test_import_and_exceptions(self):
        import hub.server as s
        self.assertTrue(hasattr(s, "InvalidContentLength"))
        self.assertTrue(hasattr(s, "PayloadTooLarge"))
        self.assertTrue(hasattr(s, "FIELD_CAPS"))
        self.assertTrue(hasattr(s, "_labels_ok"))
        self.assertTrue(hasattr(s, "_scan_state_ok"))

if __name__ == "__main__":
    unittest.main()
