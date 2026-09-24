# // spec: coh-id-04, coh-rt-01, coh-rt-08
"""The pinned evaluator identity, end to end: the execution-profile registry
(coh-id-04), the pipeline check that the pin actually RESOLVES, the
template's agreement with the registry, and a real-container smoke against
the pinned bytes.

Split out of test_hub_coherence_container.py (file-size limit). The division
is WHICH bytes run versus HOW the driver runs them: everything here decides
or verifies the identity, that file exercises the launcher/driver contract
against it.
"""
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import schemacheck  # noqa: E402
from hub.coherence.profiles import (ProfileRegistryError,  # noqa: E402
                                    check_launch_digest, load_registry,
                                    resolve_profile, validate_registry)

REPO = Path(__file__).resolve().parent.parent
REGISTRY = REPO / "container" / "execution-profiles.json"
REGISTRY_SCHEMA = (REPO / "openspec/changes/devgate-spec-coherence-service"
                          "/schemas/execution-profiles.schema.json")

VALID_REGISTRY = {
    "schema": "execution-profiles",
    "image": "localhost/devgate-coherence",
    "profiles": [
        {"label": "linux-amd64-v1", "platform": "linux/amd64",
         "image_manifest_digest": "sha256:" + "a" * 64,
         "base_image": "docker.io/library/python@sha256:" + "b" * 64,
         "semantic_equivalence_group": "default", "built": "2026-09-18"},
    ],
}

class TestExecutionProfilesRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = load_registry(REGISTRY)

    def test_real_registry_loads_and_validates(self):
        self.assertEqual(self.reg["schema"], "execution-profiles")
        labels = [p["label"] for p in self.reg["profiles"]]
        self.assertIn("linux-amd64-v1", labels)

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
        p = resolve_profile(self.reg, "linux-amd64-v1")
        self.assertRegex(p["image_manifest_digest"], r"^sha256:[0-9a-f]{64}$")
        check_launch_digest(self.reg, "linux-amd64-v1",
                            p["image_manifest_digest"])
        with self.assertRaises(ProfileRegistryError) as cm:
            check_launch_digest(self.reg, "linux-amd64-v1",
                                "sha256:" + "0" * 64)
        self.assertEqual(str(cm.exception),
                         "profile-digest-mismatch:linux-amd64-v1")

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
        bad["profiles"][0]["label"] = "linux-amd64-v1"
        bad["profiles"].append(dict(bad["profiles"][0]))
        with self.assertRaises(ProfileRegistryError) as cm:
            validate_registry(bad)
        self.assertEqual(str(cm.exception),
                         "duplicate-profile-label:linux-amd64-v1")
        bad = json.loads(json.dumps(VALID_REGISTRY))
        bad["profiles"][0]["image_manifest_digest"] = "sha256:short"
        with self.assertRaises(ProfileRegistryError):
            validate_registry(bad)
        bad = json.loads(json.dumps(VALID_REGISTRY))
        bad["profiles"][0]["platform"] = "linux/riscv64"
        with self.assertRaises(ProfileRegistryError):
            validate_registry(bad)


CI = REPO / ".github/workflows/ci.yml"


class TestIdentityChainInCI(unittest.TestCase):
    """The pipeline must check the identity on the axis consumers use.

    Measured 2026-09-23: `podman image inspect` of a LOCALLY BUILT image
    reports a digest the registry never serves — the push re-encodes the
    manifest (local 2eff3fd9…/9fd3b543…, registry manifest f470110c… for the
    same bytes). A check comparing that local number to the registry record is
    therefore config-against-config: it agrees with itself while shipping a
    pin no consumer can fetch, which is exactly what the S4 pin was.
    Fetchability is the checkable property, and it is the one the consumer
    chain depends on.
    """

    def setUp(self):
        self.text = CI.read_text(encoding="utf-8")

    def test_ci_verifies_the_recorded_identity_is_fetchable(self):
        self.assertIn("container/execution-profiles.json", self.text,
                      "CI never reads the identity registry")
        self.assertRegex(
            self.text, r'podman pull[^\n]*"\$IMAGE@\$RECORDED"',
            "CI does not pull the recorded image@digest: nothing in the "
            "pipeline proves the pinned identity resolves from a registry")

    def test_ci_never_compares_a_local_build_digest_to_the_record(self):
        """The defect signature: a locally built tag's `.Digest` read as the
        published identity.

        Banned outright rather than only banned-when-compared: the value is
        not merely unused here, it is WRONG for every purpose in this
        pipeline (the registry does not serve it), and printing it is how the
        unpullable pin was recorded in the first place. Diagnostics want the
        served digest — `$IMAGE:main`, resolved after the push.
        """
        self.assertNotIn(
            "image inspect --format '{{.Digest}}' devgate-coherence", self.text,
            "CI compares a locally built image's digest to the identity "
            "record — a different axis; the registry never serves that value")


PROFILE_LABEL = "linux-amd64-v1"


def pinned_ref() -> str:
    """The image@digest the pinned registry says consumers must launch."""
    reg = load_registry(REGISTRY)
    prof = resolve_profile(reg, PROFILE_LABEL)
    return f"{reg['image']}@{prof['image_manifest_digest']}"


def ensure_pinned_image(test) -> str:
    """Make the PINNED image available locally, or skip (never pass).

    The subject of a real-container test is the pinned identity, not a local
    rebuild: measured 2026-09-23, the same source built here and on the hosted
    runner produced different config digests, so a local tag is a DIFFERENT
    artifact than the bytes consumers execute — running it would certify bytes
    nobody runs. Present already, or pull the pinned ref (what a consumer
    does); if neither, the test cannot evaluate and says so.
    """
    ref = pinned_ref()
    if subprocess.run(["podman", "image", "exists", ref],
                      capture_output=True).returncode == 0:
        return ref
    r = subprocess.run(["podman", "pull", "--quiet", ref],
                       capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        test.skipTest(f"pinned image {ref} is not present and could not be "
                      f"pulled: {r.stderr.strip()[:200]}")
    return ref




class TestIdentityChainPreconditions(unittest.TestCase):
    """The identity guard depends on a checkout property; assert it here.

    `test_the_pinned_commit_carries_the_pinned_identity` (template suite)
    resolves DEVGATE_PIN with `git show <pin>:container/execution-profiles.json`,
    which a default fetch-depth-1 checkout cannot answer. The failure mode is
    not a red guard — it is a guard that cannot run at all, which is the shape
    this whole slice exists to remove. On 2026-09-24 that is exactly what
    happened: the fetch-depth fix was written and forgotten, so the guard went
    red on hosted for a reason unrelated to the pin.
    """

    def test_the_tests_job_checks_out_full_history(self):
        text = CI.read_text(encoding="utf-8")
        m = re.search(r"\n  tests:\n(.*?)(?=\n  [a-z][a-z0-9-]*:\n|\Z)",
                      text, re.S)
        self.assertTrue(m, "ci.yml declares no tests job")
        if "fetch-depth: 0" not in m.group(1):
            self.fail("the tests job checks out shallow — the pin guard reads "
                      "the registry out of the pinned commit's tree, so it "
                      "needs the object: add `with: fetch-depth: 0`")


class TestPinnedImageHelper(unittest.TestCase):
    """`ensure_pinned_image` decides what every real-container test runs.

    The bug this exists for: the first cut returned the ref only on the
    already-present path and fell through to `None` after a SUCCESSFUL pull —
    so on a fresh runner, where the pull is the path actually taken, every
    caller got `None` and the smoke died on a TypeError. The local run was
    green because the local image was already attached, so the pull path never
    executed here. Mocked, so both paths are exercised on any host.
    """

    def _fake(self, codes):
        calls = []

        def fake(argv, **kw):
            calls.append(argv)
            return mock.MagicMock(returncode=codes.pop(0), stdout="",
                                  stderr="")

        return calls, fake

    def test_pull_path_returns_the_ref(self):
        calls, fake = self._fake([1, 0])          # absent, then the pull lands
        with mock.patch.object(subprocess, "run", side_effect=fake):
            self.assertEqual(ensure_pinned_image(self), pinned_ref())
        self.assertEqual(calls[1][:3], ["podman", "pull", "--quiet"])

    def test_present_path_returns_the_ref_without_pulling(self):
        calls, fake = self._fake([0])
        with mock.patch.object(subprocess, "run", side_effect=fake):
            self.assertEqual(ensure_pinned_image(self), pinned_ref())
        self.assertEqual(len(calls), 1, "an attached image must not be pulled")

    def test_unavailable_image_skips_rather_than_passing(self):
        _, fake = self._fake([1, 1])              # absent, and the pull fails
        with mock.patch.object(subprocess, "run", side_effect=fake):
            with self.assertRaises(unittest.SkipTest):
                ensure_pinned_image(self)

@unittest.skipUnless(shutil.which("podman"), "podman not available")
class TestImageSmoke(unittest.TestCase):
    """Real-sandbox smoke: the PINNED image must run the service CLI under
    the launcher's enforced flag set (isolation suite is not satisfied by
    Dockerfile inspection alone)."""

    def setUp(self):
        self.IMAGE = ensure_pinned_image(self)

    def test_service_runs_under_enforced_flags(self):
        args = ["podman", "run", "--rm",
                "--read-only", "--read-only-tmpfs",
                "--cap-drop=ALL", "--security-opt=no-new-privileges",
                "--network=none", self.IMAGE, "--help"]
        r = subprocess.run(args, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("usage: hub.coherence", r.stdout)

