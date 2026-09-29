"""Real-pinned-image end-to-end tests (coh-rt-08, coh-rt-09).

Requires podman plus the pinned image (ensure_pinned_image skips honestly when
it cannot be pulled). Unit-level container checks live in
tests/test_hub_coherence_container.py.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import container_exec as ce  # noqa: E402
from hub.coherence import schemacheck  # noqa: E402,F401
from tests.test_coherence_image_identity import ensure_pinned_image  # noqa: E402
from tests.test_hub_coherence_container import DRIVER_API, REGISTRY, launch_cfg  # noqa: E402

@unittest.skipUnless(shutil.which("podman"), "podman not available")
class TestContainerExecReal(unittest.TestCase):
    """End-to-end against the real pinned image (coh-rt-08, coh-rt-09):

    - the image carries its own frozen schemas (an in-image schema load
      must succeed — F1: the image once shipped without them and every
      invocation failed at first load);
    - a VALID request completes with a non-ERROR decision (a broken
      service cannot satisfy this — the rejection case alone cannot
      distinguish an honest exit-30 from a contract-load failure);
    - an in-container honest rejection relays exit 30 AND its envelope
      reason names the invalid input, not an I/O error."""

    IMAGE = "localhost/devgate-coherence"

    def setUp(self):
        # The image pin is the whole point of this class (coh-rt-01): resolve
        # it through the shared identity helper and run THAT ref, never a
        # local tag — a local build is a different artifact than the bytes
        # consumers execute. Missing + unpullable skips (honestly), a gate that
        # runs the wrong ref is worse than one that cannot evaluate.
        self.IMAGE = ensure_pinned_image(self)
        self.tmp = Path(tempfile.mkdtemp(prefix="dg-cer-"))
        self.out = self.tmp / "out"
        self.out.mkdir()
        # The container's mapped uid must be able to write the output bind.
        os.chmod(self.out, 0o777)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _podman_base(self):
        return ["podman", "run", "--rm",
                "--read-only", "--read-only-tmpfs",
                "--cap-drop=ALL", "--security-opt=no-new-privileges",
                "--network=none"]

    def test_schemas_present_in_image(self):
        # coh-rt-08: the service loads its frozen contracts from inside the
        # image — package-relative resolution (F1 fix) must resolve there.
        r = subprocess.run(
            self._podman_base() + ["--entrypoint", "python3", self.IMAGE,
                                   "-c",
                                   "from hub.coherence import schemacheck;"
                                   " schemacheck.load('request.schema.json');"
                                   " schemacheck.load('result.schema.json')"],
            capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0,
                         f"schema load inside image failed: {r.stderr}")

    def test_incontainer_valid_request_passes(self):
        # coh-rt-09: a valid request reaches a non-ERROR decision inside the
        # container. The fixture world is real on disk (digests verify);
        # stage=1 + a satisfying assertion set yields PASS / exit 0.
        from tests.fixtures.coherence import fixtures as fx
        world = self.tmp / "world"
        world.mkdir()
        req_path, _world_out = fx.build_root(world)
        req = json.loads(Path(req_path).read_text())
        # The output bind must lie OUTSIDE every mount source (round-7
        # finding 4): point outputs at tmp/out, mounted world at /input.
        req["outputs"] = str(self.out)
        rp = self.tmp / "request.json"
        rp.write_text(json.dumps(req))
        cfg = launch_cfg()
        cfg["mounts"] = [{"source": str(world), "target": "/input",
                          "readonly": True}]
        cp = self.tmp / "launch.json"
        cp.write_text(json.dumps(cfg))
        rc = ce.run_containerized(str(rp), str(cp), str(REGISTRY))
        self.assertEqual(rc, 0, "valid in-container request must relay PASS")
        res = json.loads((self.out / "result.json").read_text())
        self.assertEqual(res["decision"], "PASS")
        self.assertIsNone(res.get("error"),
                          "PASS relay must not carry an error field")

    def test_incontainer_rejection_relays_exit30(self):
        req = {"api_version": DRIVER_API, "outputs": str(self.out)}
        rp = self.tmp / "request.json"
        rp.write_text(json.dumps(req), encoding="utf-8")
        cfg = launch_cfg()
        cfg["mounts"] = []
        cp = self.tmp / "launch.json"
        cp.write_text(json.dumps(cfg), encoding="utf-8")
        rc = ce.run_containerized(str(rp), str(cp), str(REGISTRY))
        res = json.loads((self.out / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(rc, 30, res)
        self.assertEqual(res["decision"], "ERROR")
        # coh-rt-09: an honest rejection names the invalid input. A reason
        # that reports a missing file means the image cannot load its own
        # contracts — exactly the F1 failure this suite must catch.
        reason = res.get("error", {}).get("reason", "")
        self.assertNotIn("No such file or directory", reason,
                         "contract schema missing in image — F1 regression")
        self.assertIn("missing required property", reason,
                      f"rejection must name the invalid input, got: {reason}")


if __name__ == "__main__":
    unittest.main()

