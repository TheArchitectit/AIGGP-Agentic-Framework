# // spec: coh-rt-01, coh-rt-02, coh-rt-05, coh-rt-07, coh-id-04, coh-dec-04
"""Container increment suite: digest-pinned Containerfile (coh-rt-01),
execution-profile registry integrity (coh-id-04), the containerized-execution
driver's exit-code mapping (coh-rt-05, coh-rt-07, coh-dec-04), and a
real-Podman smoke run under the launcher's enforced flag set. All fixtures
synthetic (R9).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import container_exec as ce
from hub.coherence import schemacheck
from hub.coherence.launcher import LaunchRun
from hub.coherence.profiles import (ProfileRegistryError, check_launch_digest,
                                    load_registry, resolve_profile,
                                    validate_registry)

REPO = Path(__file__).resolve().parent.parent
CONTAINERFILE = REPO / "container/Containerfile"
REGISTRY = REPO / "container/execution-profiles.json"
REGISTRY_SCHEMA = (REPO / "openspec/changes/devgate-spec-coherence-service"
                          "/schemas/execution-profiles.schema.json")

VALID_REGISTRY = {
    "schema": "execution-profiles",
    "image": "localhost/devgate-coherence",
    "profiles": [
        {"label": "linux/amd64-baseline", "platform": "linux/amd64",
         "image_manifest_digest": "sha256:" + "a" * 64,
         "base_image": "docker.io/library/python@sha256:" + "b" * 64,
         "semantic_equivalence_group": "default", "built": "2026-09-18"},
    ],
}


def _lines(text, directive):
    return [ln for ln in text.splitlines()
            if ln.strip().startswith(directive)]


class TestContainerfile(unittest.TestCase):
    def setUp(self):
        self.text = CONTAINERFILE.read_text(encoding="utf-8")

    def test_from_is_digest_pinned(self):
        froms = _lines(self.text, "FROM ")
        self.assertEqual(len(froms), 1, "exactly one FROM")
        self.assertRegex(froms[0], r"^FROM [a-z0-9./-]+@sha256:[0-9a-f]{64}$",
                         "base must be pinned by digest (coh-rt-01)")

    def test_no_tag_pinned_from(self):
        self.assertNotRegex(self.text, r"^FROM \S+:[A-Za-z0-9._-]+\s*$",
                            "tag-pinned FROM would violate coh-rt-01")

    def test_user_is_non_root(self):
        users = _lines(self.text, "USER ")
        self.assertEqual(len(users), 1)
        user = users[0].split()[1]
        self.assertNotIn(user, ("root", "0"),
                         "image must default to non-root (coh-rt-02)")

    def test_entrypoint_runs_the_service(self):
        entry = _lines(self.text, "ENTRYPOINT ")
        self.assertEqual(len(entry), 1)
        self.assertIn('"python3", "-m", "hub.coherence"', entry[0])

    def test_no_network_or_installer_in_run(self):
        for run in _lines(self.text, "RUN "):
            for banned in ("curl", "wget", "pip install"):
                self.assertNotIn(banned, run,
                                 f"build-time {banned} would break the "
                                 "no-network/no-installer profile")


class TestExecutionProfilesRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = load_registry(REGISTRY)

    def test_real_registry_loads_and_validates(self):
        self.assertEqual(self.reg["schema"], "execution-profiles")
        labels = [p["label"] for p in self.reg["profiles"]]
        self.assertIn("linux/amd64-baseline", labels)

    def test_registry_matches_its_frozen_schema(self):
        schema = json.loads(REGISTRY_SCHEMA.read_text(encoding="utf-8"))
        errs = schemacheck.validate(json.loads(REGISTRY.read_text()), schema)
        self.assertEqual(errs, [], f"registry violates its schema: {errs}")

    def test_frozen_schema_is_strict(self):
        schema = json.loads(REGISTRY_SCHEMA.read_text(encoding="utf-8"))

        def walk(node, path):
            if isinstance(node, dict):
                if node.get("type") == "object" and "properties" in node:
                    self.assertIs(node.get("additionalProperties"), False,
                                  f"{path}: schema objects must be strict")
                for k, v in node.items():
                    walk(v, f"{path}/{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}/{i}")

        walk(schema, "$")

    def test_resolve_profile_and_mismatch(self):
        p = resolve_profile(self.reg, "linux/amd64-baseline")
        self.assertRegex(p["image_manifest_digest"], r"^sha256:[0-9a-f]{64}$")
        check_launch_digest(self.reg, "linux/amd64-baseline",
                            p["image_manifest_digest"])
        with self.assertRaises(ProfileRegistryError) as cm:
            check_launch_digest(self.reg, "linux/amd64-baseline",
                                "sha256:" + "0" * 64)
        self.assertEqual(str(cm.exception),
                         "profile-digest-mismatch:linux/amd64-baseline")

    def test_unknown_profile_unresolvable(self):
        with self.assertRaises(ProfileRegistryError) as cm:
            resolve_profile(self.reg, "linux/riscv64-baseline")
        self.assertEqual(str(cm.exception),
                         "undeclared-profile:linux/riscv64-baseline")

    def test_registry_shape_rejections(self):
        bad = dict(VALID_REGISTRY)
        bad["schema"] = "nope"
        with self.assertRaises(ProfileRegistryError):
            validate_registry(bad)
        bad = json.loads(json.dumps(VALID_REGISTRY))
        bad["profiles"][0]["label"] = "linux/amd64-baseline"
        bad["profiles"].append(dict(bad["profiles"][0]))
        with self.assertRaises(ProfileRegistryError) as cm:
            validate_registry(bad)
        self.assertEqual(str(cm.exception),
                         "duplicate-profile-label:linux/amd64-baseline")
        bad = json.loads(json.dumps(VALID_REGISTRY))
        bad["profiles"][0]["image_manifest_digest"] = "sha256:short"
        with self.assertRaises(ProfileRegistryError):
            validate_registry(bad)
        bad = json.loads(json.dumps(VALID_REGISTRY))
        bad["profiles"][0]["platform"] = "linux/riscv64"
        with self.assertRaises(ProfileRegistryError):
            validate_registry(bad)


@unittest.skipUnless(shutil.which("podman"), "podman not available")
class TestImageSmoke(unittest.TestCase):
    """Real-sandbox smoke: the built image must run the service CLI under
    the launcher's enforced flag set (isolation suite is not satisfied by
    Dockerfile inspection alone)."""

    IMAGE = "localhost/devgate-coherence"

    def setUp(self):
        r = subprocess.run(["podman", "image", "exists", self.IMAGE],
                           capture_output=True)
        if r.returncode != 0:
            self.skipTest("devgate-coherence image not built locally")

    def test_service_runs_under_enforced_flags(self):
        args = ["podman", "run", "--rm",
                "--read-only", "--read-only-tmpfs",
                "--cap-drop=ALL", "--security-opt=no-new-privileges",
                "--network=none", self.IMAGE, "--help"]
        r = subprocess.run(args, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("usage: hub.coherence", r.stdout)


DRIVER_API = "devgate.spec-coherence/v1"


def launch_cfg(manifest=None):
    """Launch config whose profile/digest resolve against the real registry."""
    dig = load_registry(REGISTRY)["profiles"][0]["image_manifest_digest"]
    mdig = manifest or dig
    return {
        "image": "localhost/devgate-coherence@" + mdig,
        "user": "1000:1000",
        "read_only_rootfs": True,
        "cap_drop": ["ALL"],
        "cap_add": [],
        "network": "none",
        "mounts": [{"source": "/srv/inputs/pkg", "target": "/input",
                    "readonly": True}],
        "scratch": {"size": "64m"},
        "limits": {"memory": "256m", "cpus": "1.0", "time_s": 60,
                   "pids": 64, "nofile": 128, "output_bytes": 65536},
        "profile": "linux/amd64-baseline",
        "image_manifest_digest": mdig,
    }


def driver_request():
    return {"api_version": DRIVER_API,
            "subject": {"root": "/srv/inputs/pkg"}, "outputs": ""}


class TestContainerExec(unittest.TestCase):
    """Exit-code mapping of the containerized driver (coh-rt-05, coh-dec-04):
    a launch rejected before assertions is exit 30; a container killed for
    limit exhaustion, or a completed run whose exit code and result bundle
    disagree (including podman-level non-contract codes), is ERROR
    execution 32."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dg-ce-"))
        self.out = self.tmp / "out"
        self.out.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, name, obj):
        p = self.tmp / name
        p.write_text(obj if isinstance(obj, str) else json.dumps(obj))
        return str(p)

    def _run(self, req, cfg, run_patch=None):
        req = dict(req)
        if not req.get("outputs"):
            req["outputs"] = str(self.out)
        rp = self._write("request.json", req)
        cp = self._write("launch.json", cfg)
        with mock.patch.object(ce.launcher, "run",
                               return_value=LaunchRun(0, b"", "completed")) as m:
            if run_patch is not None:
                m.side_effect = run_patch
            rc = ce.run_containerized(rp, cp, str(REGISTRY))
        return rc, m

    def _envelope(self):
        for d in (self.out, self.tmp):
            p = d / "result.json"
            if p.exists():
                return json.loads(p.read_text())
        self.fail("no result.json written")

    def test_malformed_launch_config_is_exit30(self):
        rp = self._write("request.json", driver_request())
        rc = ce.run_containerized(rp, str(self.tmp / "missing.json"),
                                  str(REGISTRY))
        self.assertEqual(rc, 30)
        self.assertEqual(self._envelope()["error"]["class"], "invalid-input")

    def test_launch_rejection_is_exit30_before_assertions(self):
        cfg = launch_cfg()
        cfg["image"] = "localhost/devgate-coherence:latest"
        rc, m = self._run(driver_request(), cfg)
        self.assertEqual(rc, 30)
        env = self._envelope()
        self.assertEqual(env["error"]["class"], "invalid-input")
        self.assertIn("tag-only-image", env["error"]["reason"])
        m.assert_not_called()

    def test_registry_digest_mismatch_rejected_before_run(self):
        rc, m = self._run(driver_request(), launch_cfg("sha256:" + "0" * 64))
        self.assertEqual(rc, 30)
        self.assertIn("profile-digest-mismatch",
                      self._envelope()["error"]["reason"])
        m.assert_not_called()

    def test_unmounted_root_rejected(self):
        cfg = launch_cfg()
        cfg["mounts"] = [{"source": "/srv/other", "target": "/in",
                          "readonly": True}]
        rc, m = self._run(driver_request(), cfg)
        self.assertEqual(rc, 30)
        self.assertIn("unmounted-root:subject",
                      self._envelope()["error"]["reason"])
        m.assert_not_called()

    def test_roots_rewritten_and_staged_readable(self):
        captured = {}

        def fake_run(ctx, *, output_dir, container_args):
            captured["args"] = container_args
            # The driver stages the rewritten request inside the output
            # directory itself, so in-container envelopes (emitted beside the
            # request file) land on the designated output bind.
            captured["staged"] = json.loads(
                (Path(output_dir) / ce.STAGED_REQUEST_NAME).read_text())
            (output_dir / "result.json").write_text('{"decision": "PASS"}')
            return LaunchRun(0, b"", "completed")

        rc, _ = self._run(driver_request(), launch_cfg(), fake_run)
        self.assertEqual(rc, 0)
        self.assertEqual(captured["args"],
                         ["--request", "/output/" + ce.STAGED_REQUEST_NAME])
        self.assertEqual(captured["staged"]["subject"]["root"], "/input")
        self.assertEqual(captured["staged"]["outputs"], "/output")

    def test_timeout_maps_to_exit32(self):
        rc, _ = self._run(driver_request(), launch_cfg(),
                          lambda *a, **kw: LaunchRun(0, b"", "timeout"))
        self.assertEqual(rc, 32)
        env = self._envelope()
        self.assertEqual(env["error"]["class"], "execution")
        self.assertIn("launch-timeout", env["error"]["reason"])

    def test_output_overflow_maps_to_exit32(self):
        rc, _ = self._run(driver_request(), launch_cfg(),
                          lambda *a, **kw: LaunchRun(0, b"", "output-overflow"))
        self.assertEqual(rc, 32)
        self.assertIn("launch-output-overflow",
                      self._envelope()["error"]["reason"])

    def test_missing_result_bundle_is_error(self):
        rc, _ = self._run(driver_request(), launch_cfg())
        self.assertEqual(rc, 32)
        self.assertIn("exit-code contract",
                      self._envelope()["error"]["reason"])

    def test_noncontract_exit_code_is_error(self):
        # A podman-level failure (e.g. exit 125) is never a contract exit and
        # must not slip through as "None agrees with None".
        rc, _ = self._run(driver_request(), launch_cfg(),
                          lambda *a, **kw: LaunchRun(125, b"", "completed"))
        self.assertEqual(rc, 32)
        self.assertIn("125", self._envelope()["error"]["reason"])

    def test_coherent_fail_relayed(self):
        def fake_run(ctx, *, output_dir, container_args):
            (output_dir / "result.json").write_text('{"decision": "FAIL"}')
            return LaunchRun(20, b"", "completed")

        rc, _ = self._run(driver_request(), launch_cfg(), fake_run)
        self.assertEqual(rc, 20)

    def test_outputs_nul_rejected(self):
        req = driver_request()
        req["outputs"] = "o\x00ut"
        rc, m = self._run(req, launch_cfg())
        self.assertEqual(rc, 30)
        self.assertIn("NUL", self._envelope()["error"]["reason"])
        m.assert_not_called()

    def test_outputs_inside_mount_source_rejected(self):
        # Round-7 finding 4: staging (or writing any envelope) inside a
        # mount source would pollute the input tree being evaluated — the
        # output bind must lie outside every input source.
        inputs = self.tmp / "inputs"
        inputs.mkdir()
        cfg = launch_cfg()
        cfg["mounts"] = [{"source": str(inputs), "target": "/input",
                          "readonly": True}]
        req = driver_request()
        req["subject"]["root"] = str(inputs / "pkg")
        for outs in (str(inputs / "results"), str(inputs)):
            req["outputs"] = outs
            rc, m = self._run(req, cfg)
            self.assertEqual(rc, 30)
            # The rejection envelope lands in the caller-declared outputs
            # dir itself (inside the mount source, as declared).
            env = json.loads((Path(outs) / "result.json").read_text())
            self.assertIn("outputs-inside-mount-source",
                          env["error"]["reason"])
            m.assert_not_called()

    def test_contradictory_error_field_is_error(self):
        # Round-7 finding 3 (coh-dec-01): exit 0 with decision PASS but a
        # non-null error field is an exit/result disagreement — never
        # relayed as the permissive signal.
        def fake_run(ctx, *, output_dir, container_args):
            (output_dir / "result.json").write_text(
                json.dumps({"decision": "PASS",
                           "error": {"class": "execution", "reason": "hidden",
                                     "stage": "evaluation"}}))
            return LaunchRun(0, b"", "completed")

        rc, _ = self._run(driver_request(), launch_cfg(), fake_run)
        self.assertEqual(rc, 32)
        env = self._envelope()
        self.assertEqual(env["error"]["class"], "execution")
        self.assertIn("error field", env["error"]["reason"])

    def test_staged_request_written_atomically(self):
        # Round-7: the staged request goes through result.emit (fsync +
        # rename) — an interrupted staging leaves a temp fragment, never a
        # half-written canonical request.
        emitted = []
        real_emit = ce.result.emit

        def spy(path, payload):
            emitted.append(Path(path).name)
            return real_emit(path, payload)

        def fake_run(ctx, *, output_dir, container_args):
            (output_dir / "result.json").write_text('{"decision": "PASS"}')
            return LaunchRun(0, b"", "completed")

        with mock.patch.object(ce.result, "emit", side_effect=spy):
            rc, _ = self._run(driver_request(), launch_cfg(), fake_run)
        self.assertEqual(rc, 0)
        self.assertIn(ce.STAGED_REQUEST_NAME, emitted)


@unittest.skipUnless(shutil.which("podman"), "podman not available")
class TestContainerExecReal(unittest.TestCase):
    """End-to-end against the real pinned image: an in-container honest
    rejection must relay through the exit-code agreement check as exit 30."""

    def setUp(self):
        r = subprocess.run(
            ["podman", "image", "exists", "localhost/devgate-coherence"],
            capture_output=True)
        if r.returncode != 0:
            self.skipTest("devgate-coherence image not built locally")
        self.tmp = Path(tempfile.mkdtemp(prefix="dg-cer-"))
        self.out = self.tmp / "out"
        self.out.mkdir()
        # The container's mapped uid must be able to write the output bind.
        os.chmod(self.out, 0o777)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_incontainer_rejection_relays_exit30(self):
        req = {"api_version": DRIVER_API, "outputs": str(self.out)}
        rp = self.tmp / "request.json"
        rp.write_text(json.dumps(req))
        cfg = launch_cfg()
        cfg["mounts"] = []
        cp = self.tmp / "launch.json"
        cp.write_text(json.dumps(cfg))
        rc = ce.run_containerized(str(rp), str(cp), str(REGISTRY))
        res = json.loads((self.out / "result.json").read_text())
        self.assertEqual(rc, 30, res)
        self.assertEqual(res["decision"], "ERROR")


if __name__ == "__main__":
    unittest.main()
