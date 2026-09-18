# // spec: coh-rt-01, coh-id-04
"""Container increment suite: digest-pinned Containerfile (coh-rt-01),
execution-profile registry integrity (coh-id-04), and a real-Podman smoke
run under the launcher's enforced flag set. All fixtures synthetic (R9).
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import schemacheck
from hub.coherence.profiles import (ProfileRegistryError, check_launch_digest,
                                    load_registry, resolve_profile,
                                    validate_registry)

REPO = Path(__file__).resolve().parent.parent
CONTAINERFILE = REPO / "container/Containerfile"
REGISTRY = REPO / "container/execution-profiles.json"
REGISTRY_SCHEMA = REPO / "container/execution-profiles.schema.json"

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


if __name__ == "__main__":
    unittest.main()
