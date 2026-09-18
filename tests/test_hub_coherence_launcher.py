# // spec: coh-rt-01, coh-rt-02, coh-rt-05, coh-rt-07, coh-id-04
"""Launcher validation suite: every rejection class of the isolation
profile, self-report reconciliation, and enforced podman arg derivation.
All fixtures synthetic (R9).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence.launcher import LaunchError, podman_args, validate_launch

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
                   "pids": 128, "output_bytes": 1048576},
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
        for k, v in (("time_s", 0), ("cpus", "x"), ("pids", -1)):
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
        self.args = podman_args(self.ctx, scratch_dir=Path("/tmp/sc"),
                                output_dir=Path("/tmp/out"))

    def test_args_enforce_isolation(self):
        for flag in ("--read-only", "--read-only-tmpfs", "--user=1000:1000",
                     "--cap-drop=ALL", "--network=none",
                     "--security-opt=no-new-privileges",
                     "--memory=512000000", "--cpus=1.0", "--pids-limit=128"):
            self.assertIn(flag, self.args)

    def test_scratch_and_output_binds(self):
        self.assertIn("--tmpfs", self.args)
        self.assertIn("/scratch:size=512000000,noexec,nodev", self.args)
        self.assertIn("/tmp/sc:/scratch", self.args)
        self.assertIn("/tmp/out:/output", self.args)

    def test_input_mounts_readonly_and_sorted(self):
        cfg = base_cfg()
        cfg["mounts"] = [
            {"source": "/srv/b", "target": "/z", "readonly": True},
            {"source": "/srv/a", "target": "/a", "readonly": True},
        ]
        args = podman_args(validate_launch(cfg, PROFILES),
                           scratch_dir=Path("/s"), output_dir=Path("/o"))
        binds = [a for a in args if a.startswith("/srv/")]
        self.assertEqual(binds, ["/srv/a:/a:ro", "/srv/b:/z:ro"])

    def test_image_is_last_arg(self):
        self.assertEqual(self.args[-1], "ghcr.io/example/coherence@" + SHA)


if __name__ == "__main__":
    unittest.main()
