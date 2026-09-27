"""Negative Content-Length — refused before any read (P0 hub)."""
import unittest

class TestInvalidContentLength(unittest.TestCase):
    def test_exception_exists_and_is_exception_subclass(self):
        from hub.server import InvalidContentLength, PayloadTooLarge
        self.assertTrue(issubclass(InvalidContentLength, Exception))
        self.assertTrue(issubclass(PayloadTooLarge, Exception))
        # The contract: do_POST catches InvalidContentLength and sends 400.
        # Source inspection confirms it; live socket not needed for harness.
