# // spec: coh-rt-01, coh-rt-02, coh-rt-05, coh-rt-07, coh-id-04
"""Launcher validation suite: every rejection class of the isolation
profile, self-report reconciliation, and enforced podman arg derivation.
All fixtures synthetic (R9).
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence.launcher import (LaunchError, podman_args, run,
                                    validate_launch)

SHA = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
PROFILES = ["linux/amd64-baseline", "linux/arm64-baseline"]


def base_cfg():
    return {
        "image": "ghcr.io/example/coherence@" + SHA,
        "user": "1000:1000",
        "read_only_rootfs": True,
        "cap_drop": ["ALL"],
        "cap_add": [],
        "network": "none",
        "mounts": [{"source": "/srv/inputs/pkg", "target": "/input",
                    "readonly": True}],
        "scratch": {"size": "512m"},
        "limits": {"memory": "512m", "cpus": "1.0", "time_s": 600,
                   "pids": 128, "nofile": 256, "output_bytes": 1048576},
        "profile": "linux/amd64-baseline",
        "image_index_digest": SHA,
        "image_manifest_digest": SHA_B,
    }


class TestLauncherValidation(unittest.TestCase):
    def test_valid_config_yields_effective_context(self):
        ctx = validate_launch(base_cfg(), PROFILES)
        self.assertEqual(ctx["image"], "ghcr.io/example/coherence@" + SHA)
        self.assertEqual(ctx["user"], "1000:1000")
        self.assertTrue(ctx["read_only_rootfs"])
        self.assertEqual(ctx["cap_drop"], ["ALL"])
        self.assertEqual(ctx["network"], "none")
        self.assertEqual(ctx["scratch_bytes"], 512 * 10**6)
        self.assertEqual(ctx["limits"]["memory"], 512 * 10**6)
        self.assertEqual(ctx["limits"]["cpus"], 1.0)
        self.assertEqual(ctx["limits"]["pids"], 128)
        self.assertEqual(ctx["limits"]["time_s"], 600)
        self.assertEqual(ctx["limits"]["output_bytes"], 1048576)
        self.assertEqual(ctx["profile"], "linux/amd64-baseline")
        self.assertEqual(ctx["image_index_digest"], SHA)
        self.assertEqual(ctx["image_manifest_digest"], SHA_B)

    # --- coh-rt-01: digest-pinned invocation ---
    def test_tag_only_image_rejected(self):
        for ref in ("ghcr.io/example/coherence:latest", "ghcr.io/example/coherence"):
            cfg = base_cfg()
            cfg["image"] = ref
            with self.assertRaises(LaunchError) as cm:
                validate_launch(cfg, PROFILES)
            self.assertEqual(str(cm.exception), "tag-only-image")

    def test_name_tag_with_digest_accepted(self):
        cfg = base_cfg()
        cfg["image"] = "ghcr.io/example/coherence:1.2.3@" + SHA
        ctx = validate_launch(cfg, PROFILES)
        self.assertEqual(ctx["image"], cfg["image"])

    def test_bad_digest_rejected(self):
        for dig in ("sha256:" + "z" * 64, "sha256:" + "a" * 32,
                    "sha256:" + "A" * 64, "md5:" + "a" * 64):
            cfg = base_cfg()
            cfg["image"] = "ghcr.io/example/coherence@" + dig
            with self.assertRaises(LaunchError):
                validate_launch(cfg, PROFILES)

    # --- coh-rt-02: user / rootfs / capabilities / network / sockets ---
    def test_root_user_rejected(self):
        for u in ("0", "0:0", "root"):
            cfg = base_cfg()
            cfg["user"] = u
            with self.assertRaises(LaunchError) as cm:
                validate_launch(cfg, PROFILES)
            self.assertEqual(str(cm.exception), "root-user")

    def test_missing_user_rejected(self):
        cfg = base_cfg()
        del cfg["user"]
        with self.assertRaises(LaunchError) as cm:
            validate_launch(cfg, PROFILES)
        self.assertEqual(str(cm.exception), "missing-field:user")

    def test_writable_rootfs_rejected(self):
        cfg = base_cfg()
        cfg["read_only_rootfs"] = False
        with self.assertRaises(LaunchError) as cm:
            validate_launch(cfg, PROFILES)
        self.assertEqual(str(cm.exception), "writable-rootfs")

    def test_cap_drop_missing_rejected(self):
        for cap in ([], None):
            cfg = base_cfg()
            if cap is None:
                del cfg["cap_drop"]
            else:
                cfg["cap_drop"] = cap
            with self.assertRaises(LaunchError) as cm:
                validate_launch(cfg, PROFILES)
            self.assertEqual(str(cm.exception), "cap-drop-missing")

    def test_cap_add_forbidden(self):
        cfg = base_cfg()
        cfg["cap_add"] = ["NET_ADMIN"]
        with self.assertRaises(LaunchError) as cm:
            validate_launch(cfg, PROFILES)
        self.assertEqual(str(cm.exception), "cap-add-forbidden")

    def test_host_network_rejected(self):
        cfg = base_cfg()
        cfg["network"] = "host"
        with self.assertRaises(LaunchError) as cm:
            validate_launch(cfg, PROFILES)
        self.assertEqual(str(cm.exception), "host-network")

    def test_non_none_network_rejected(self):
        for net in ("bridge", None):
            cfg = base_cfg()
            if net is None:
                del cfg["network"]
            else:
                cfg["network"] = net
            with self.assertRaises(LaunchError) as cm:
                validate_launch(cfg, PROFILES)
            self.assertEqual(str(cm.exception), "network-not-none")

    def test_writable_mount_rejected(self):
        cfg = base_cfg()
        cfg["mounts"] = [{"source": "/srv/inputs/pkg", "target": "/input",
                          "readonly": False}]
        with self.assertRaises(LaunchError) as cm:
            validate_launch(cfg, PROFILES)
        self.assertEqual(str(cm.exception), "writable-mount:/input")

    def test_host_socket_bind_rejected(self):
        for src in ("/var/run/docker.sock", "/run/podman/podman.sock"):
            cfg = base_cfg()
            cfg["mounts"] = [{"source": src, "target": "/sock",
                              "readonly": True}]
            with self.assertRaises(LaunchError) as cm:
                validate_launch(cfg, PROFILES)
            self.assertEqual(str(cm.exception), f"host-socket-bind:{src}")

    # --- coh-rt-07: bounded scratch ---
    def test_unbounded_scratch_rejected(self):
        for scratch in (None, {}, {"size": 0}, {"size": "abc"}):
            cfg = base_cfg()
            if scratch is None:
                del cfg["scratch"]
            else:
                cfg["scratch"] = scratch
            with self.assertRaises(LaunchError) as cm:
                validate_launch(cfg, PROFILES)
            self.assertEqual(str(cm.exception), "unbounded-scratch")

    # --- coh-rt-05: limits ---
    def test_missing_limit_rejected(self):
        cfg = base_cfg()
        del cfg["limits"]["output_bytes"]
        with self.assertRaises(LaunchError) as cm:
            validate_launch(cfg, PROFILES)
        self.assertEqual(str(cm.exception), "missing-limit:output_bytes")

    def test_bad_limit_rejected(self):
        for k, v in (("time_s", 0), ("cpus", "x"), ("pids", -1),
                     ("nofile", 0)):
            cfg = base_cfg()
            cfg["limits"][k] = v
            with self.assertRaises(LaunchError) as cm:
                validate_launch(cfg, PROFILES)
            self.assertEqual(str(cm.exception), f"bad-limit:{k}")

    # --- coh-id-04: execution-profile registry ---
    def test_undeclared_profile_rejected(self):
        cfg = base_cfg()
        cfg["profile"] = "linux/riscv64-baseline"
        with self.assertRaises(LaunchError) as cm:
            validate_launch(cfg, PROFILES)
        self.assertEqual(str(cm.exception),
                         "undeclared-profile:linux/riscv64-baseline")

    def test_missing_profile_rejected(self):
        cfg = base_cfg()
        del cfg["profile"]
        with self.assertRaises(LaunchError) as cm:
            validate_launch(cfg, PROFILES)
        self.assertEqual(str(cm.exception), "missing-field:profile")

    def test_bad_identity_digest_fields_rejected(self):
        for k in ("image_index_digest", "image_manifest_digest"):
            cfg = base_cfg()
            cfg[k] = "sha256:" + "c" * 8
            with self.assertRaises(LaunchError) as cm:
                validate_launch(cfg, PROFILES)
            self.assertEqual(str(cm.exception), f"bad-{k}")

    def test_missing_manifest_digest_rejected(self):
        # coh-id-04: the executed platform manifest digest is a
        # MUST-distinguish field, unlike the index digest ("if any").
        cfg = base_cfg()
        del cfg["image_manifest_digest"]
        with self.assertRaises(LaunchError) as cm:
            validate_launch(cfg, PROFILES)
        self.assertEqual(str(cm.exception),
                         "missing-field:image_manifest_digest")

    # --- coh-rt-02: self-report not trusted ---
    def test_self_report_mismatch_rejected(self):
        for declared in ({"network": "bridge"},
                         {"user": "0:0"},
                         {"read_only_rootfs": False},
                         {"cap_drop": ["NET_RAW"]},
                         {"profile": "linux/arm64-baseline"}):
            cfg = base_cfg()
            cfg["declared"] = declared
            with self.assertRaises(LaunchError) as cm:
                validate_launch(cfg, PROFILES)
            field = next(iter(declared))
            self.assertEqual(str(cm.exception),
                             f"self-report-mismatch:{field}")

    def test_self_report_agreement_accepted(self):
        cfg = base_cfg()
        cfg["declared"] = {"user": "1000:1000", "read_only_rootfs": True,
                           "network": "none", "cap_drop": ["ALL"],
                           "profile": "linux/amd64-baseline"}
        ctx = validate_launch(cfg, PROFILES)
        self.assertEqual(ctx["user"], "1000:1000")


class TestLauncherPodmanArgs(unittest.TestCase):
    def setUp(self):
        self.ctx = validate_launch(base_cfg(), PROFILES)
        self.args = podman_args(self.ctx, output_dir=Path("/tmp/out"))

    def test_args_enforce_isolation(self):
        for flag in ("--read-only", "--read-only-tmpfs", "--user=1000:1000",
                     "--cap-drop=ALL", "--network=none",
                     "--security-opt=no-new-privileges",
                     "--memory=512000000", "--cpus=1.0", "--pids-limit=128",
                     "nofile=256:256", "--shm-size=64m"):
            self.assertIn(flag, self.args)

    def test_every_writable_target_is_bounded(self):
        # coh-rt-07: the only writable space is the bounded scratch set plus
        # the designated output bind. Every tmpfs target carries an explicit
        # size; /dev/shm is pinned; there is NO scratch bind (tmpfs-only
        # scratch — a round-6 HIGH: duplicate /scratch destination made
        # every derived invocation unrunnable).
        for target in ("/scratch:size=512000000,noexec,nodev",
                       "/tmp:size=512000000,noexec,nodev",
                       "/run:size=512000000,noexec,nodev"):
            self.assertIn(target, self.args)
        self.assertIn("/tmp/out:/output", self.args)
        for a in self.args:
            self.assertFalse(a.startswith("/tmp/sc:"),
                             "no host bind may target /scratch")

    def test_input_mounts_readonly_and_sorted(self):
        cfg = base_cfg()
        cfg["mounts"] = [
            {"source": "/srv/b", "target": "/z", "readonly": True},
            {"source": "/srv/a", "target": "/a", "readonly": True},
        ]
        args = podman_args(validate_launch(cfg, PROFILES),
                           output_dir=Path("/o"))
        binds = [a for a in args if a.startswith("/srv/")]
        self.assertEqual(binds, ["/srv/a:/a:ro", "/srv/b:/z:ro"])

    def test_image_is_last_arg(self):
        self.assertEqual(self.args[-1], "ghcr.io/example/coherence@" + SHA)


@unittest.skipUnless(shutil.which("podman"), "podman not available")
class TestLauncherRun(unittest.TestCase):
    """Real-podman run() tests: the derived args must actually execute
    (round-6 HIGH: an arg list podman rejects is an unusable launcher), and
    the time/output limit enforcement must kill, not truncate."""

    IMAGE = "localhost/devgate-coherence"

    def setUp(self):
        r = subprocess.run(["podman", "image", "exists", self.IMAGE],
                           capture_output=True)
        if r.returncode != 0:
            self.skipTest("devgate-coherence image not built locally")
        # Use the digest the local image really has: a synthetic digest
        # makes podman attempt a registry pull.
        r = subprocess.run(["podman", "image", "inspect", "--format",
                            "{{.Digest}}", self.IMAGE],
                           capture_output=True, text=True)
        digest = r.stdout.strip()
        if not digest.startswith("sha256:"):
            self.skipTest("could not resolve local image digest")
        self.cfg = base_cfg()
        self.cfg["image"] = self.IMAGE + "@" + digest
        self.out = Path(tempfile.mkdtemp(prefix="dg-run-"))
        self.inp = Path(tempfile.mkdtemp(prefix="dg-in-"))
        (self.inp / "placeholder.txt").write_text("synthetic input (R9)\n")
        self.cfg["mounts"] = [{"source": str(self.inp),
                               "target": "/input", "readonly": True}]

    def tearDown(self):
        shutil.rmtree(self.out, ignore_errors=True)
        shutil.rmtree(self.inp, ignore_errors=True)

    def _ctx(self):
        return validate_launch(self.cfg, PROFILES)

    def test_derived_args_actually_run(self):
        rr = run(self._ctx(), output_dir=self.out, container_args=["--help"])
        self.assertEqual(rr.status, "completed")
        self.assertEqual(rr.returncode, 0, rr.output.decode(errors="replace"))
        self.assertIn(b"usage: hub.coherence", rr.output)

    def test_output_overflow_kills_not_truncates(self):
        cfg = base_cfg()
        cfg["image"] = self.IMAGE + "@" + SHA
        cfg["limits"]["output_bytes"] = 1
        rr = run(validate_launch(cfg, PROFILES), output_dir=self.out,
                 container_args=["--help"])
        self.assertEqual(rr.status, "output-overflow")
        self.assertNotEqual(rr.returncode, 0)

    def test_timeout_kills_hung_container(self):
        # No deterministic in-image hang exists (the CLI fails honest on a
        # non-regular request file), so the deadline is exercised against a
        # real pipe that never delivers data: select must hit the time
        # limit, kill the process, and report timeout — never completed.
        import os
        from unittest import mock
        import hub.coherence.launcher as L
        cfg = dict(self.cfg)
        cfg["limits"] = dict(self.cfg["limits"], time_s=1)
        ctx = validate_launch(cfg, PROFILES)
        rfd, wfd = os.pipe()
        fake = mock.MagicMock()
        fake.stdout = os.fdopen(rfd, "rb")
        fake.returncode = -9
        try:
            with mock.patch.object(L.subprocess, "Popen",
                                   return_value=fake) as popen:
                rr = run(ctx, output_dir=self.out, container_args=["--help"])
        finally:
            os.close(wfd)
            fake.stdout.close()
        self.assertEqual(rr.status, "timeout")
        self.assertEqual(rr.returncode, -9)
        fake.kill.assert_called_once()
        self.assertEqual(popen.call_args[0][0][:2], ["podman", "run"])


if __name__ == "__main__":
    unittest.main()
