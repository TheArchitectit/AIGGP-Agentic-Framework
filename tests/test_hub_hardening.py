# // spec: mon-sec-01
"""Hub runtime hardening tests (audit findings F2/F8/F9):

- request bodies above the cap are rejected with 413 before any read;
- SIGTERM shuts the hub down promptly (exit 0) while it is idle — the old
  handle_request() loop blocked in select() and PEP 475 retried after the
  handler, so systemd stop degraded to SIGKILL;
- concurrent duplicate enrollments are decided atomically (one 200, one 409).
"""
import http.client
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from hub.config import Config  # noqa: E402
from hub.server import create_server  # noqa: E402


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestBodyCap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dg-hub-")
        self.cfg = Config()
        self.cfg.data_dir = self.tmp
        self.cfg.max_body_bytes = 4096
        self.server = create_server(self.cfg, bind=("127.0.0.1", 0))
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def _post(self, path, body: bytes, declared_len=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if declared_len is not None:
            headers["Content-Length"] = str(declared_len)
        conn.request("POST", path, body=body, headers=headers)
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
        conn.close()
        return resp.status, data

    def test_oversized_body_rejected_413(self):
        body = json.dumps({"x": "a" * 8192}).encode()
        status, data = self._post("/enroll", body)
        self.assertEqual(status, 413)
        self.assertEqual(data["error"], "body_too_large")

    def test_negative_content_length_rejected(self):
        status, data = self._post("/enroll", b"{}", declared_len=-5)
        self.assertEqual(status, 400)
        self.assertEqual(data["error"], "bad_request")

    def test_invalid_content_length_rejected(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.putrequest("POST", "/enroll")
        conn.putheader("Content-Length", "abc")
        conn.endheaders()
        resp = conn.getresponse()
        self.assertEqual(resp.status, 400)
        conn.close()

    def test_normal_body_passes_cap(self):
        status, data = self._post("/enroll", json.dumps(
            {"runner_name": "r1", "repo": "o/r"}).encode())
        self.assertEqual(status, 401)  # valid size, unknown token
        self.assertEqual(data["error"], "unknown_or_revoked_token")


class TestConcurrentEnroll(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dg-hub-")
        self.cfg = Config()
        self.cfg.data_dir = self.tmp
        self.server = create_server(self.cfg, bind=("127.0.0.1", 0))
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.state = self.server.hub_state
        self.state.registry.add_enrollment_token("tok-once")
        self.state.registry.save()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_duplicate_enroll_is_atomic(self):
        barrier = threading.Barrier(2)
        results = []

        def enroll():
            body = json.dumps({"runner_name": "dup", "repo": "o/r",
                               "enrollment_token": "tok-once"}).encode()
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
            barrier.wait()
            conn.request("POST", "/enroll", body=body,
                         headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            results.append((resp.status, json.loads(resp.read().decode())))
            conn.close()

        threads = [threading.Thread(target=enroll) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        statuses = sorted(r[0] for r in results)
        # One enroll wins (200); the loser must be 409 (already enrolled) or
        # 401 (the one-time token was consumed) — never a second 200.
        self.assertEqual(statuses, [200, 409]) if 409 in statuses else \
            self.assertEqual(statuses, [200, 401])
        runners = self.state.registry.runners()
        self.assertEqual(len([r for r in runners if r["name"] == "dup"]), 1,
                         "duplicate enrollment must register exactly one runner")


class TestSignalShutdown(unittest.TestCase):
    def test_sigterm_exits_promptly_while_idle(self):
        tmp = tempfile.mkdtemp(prefix="dg-hub-")
        port = _free_port()
        env = dict(os.environ)
        env.update({"HUB_BIND_HOST": "127.0.0.1",
                    "HUB_BIND_PORT": str(port),
                    "HUB_DATA_DIR": tmp})
        proc = subprocess.Popen([sys.executable, "-m", "hub.main"],
                                cwd=str(REPO), env=env,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
        try:
            # Wait for the listener to come up.
            deadline = time.time() + 10
            while time.time() < deadline:
                try:
                    with socket.create_connection(("127.0.0.1", port), 0.2):
                        break
                except OSError:
                    time.sleep(0.05)
            else:
                self.fail("hub did not start listening")
            # Idle: no request is sent after this point.
            sent = time.time()
            proc.send_signal(signal.SIGTERM)
            try:
                code = proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                self.fail("SIGTERM did not shut the idle hub down promptly "
                          "(F2 regression: handle_request blocks until the "
                          "next request)")
            elapsed = time.time() - sent
            self.assertEqual(code, 0, proc.stdout.read() if proc.stdout else "")
            self.assertLess(elapsed, 4.5, "shutdown must be prompt")
        finally:
            if proc.poll() is None:
                proc.kill()


if __name__ == "__main__":
    unittest.main()
