"""Config boundary + dead-code removal verification."""
import unittest, os, sys

class TestConfigBoundary(unittest.TestCase):
    def test_post_init_rejects_bad_alert_channel(self):
        from hub.config import Config
        cfg = Config()
        cfg.alert_channel = "bad_value"
        with self.assertRaises(ValueError) as ctx:
            cfg.__post_init__()
        msg = str(ctx.exception)
        self.assertIn("github_issue", msg)
        self.assertIn("bad_value", msg)

    def test_post_init_rejects_negative_port(self):
        from hub.config import Config
        cfg = Config()
        cfg.bind_port = -1
        with self.assertRaises(ValueError):
            cfg.__post_init__()

class TestDeadCodeRemoved(unittest.TestCase):
    def test_no_registered_labels_in_monitor(self):
        import inspect, hub.monitor as m
        src = inspect.getsource(m)
        self.assertNotIn("registered_labels", src)
    def test_no_parse_ts_in_server(self):
        import inspect, hub.server as s
        src = inspect.getsource(s)
        self.assertNotIn("_parse_ts", src)

if __name__ == "__main__":
    unittest.main()
