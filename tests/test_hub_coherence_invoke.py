# // spec: coh-int-01, coh-int-05, coh-rt-01, coh-rt-08
"""Shared builder suite (hub/coherence/invoke.py).

The D1 defect the CI template shipped — a request heredoc with three fields
where the frozen contract requires seven — was invisible to a mutation battery
that only regex-matched shell text. This suite is the missing control: it builds
a real input tree, runs the builder, and validates the emitted objects against
the contracts that actually reject a malformed run — `request.schema.json` and
`launcher.validate_launch`. If the builder produces a request the service will
refuse at exit 30, this fails here rather than in CI.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import invoke
from hub.coherence import schemacheck
from hub.coherence import launcher
from hub.coherence.profiles import load_registry
from tests.fixtures.coherence import fixtures as fx

REPO = Path(__file__).resolve().parent.parent
REGISTRY = REPO / "container/execution-profiles.json"


class InvokeBuilderTest(unittest.TestCase):
    """Each test builds the four real input roots via the fixture, then asks
    the builder for the object a containerized run needs."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dg-invoke-"))
        # binding=True writes policy_binding into the context (round-15), so
        # the builder has a signed-identity claim to source from.
        self.req_path, self.out = fx.build_root(self.tmp, binding=True)
        root = self.tmp
        self.subject = str(root / "subject")
        self.openspec = str(root / "openspec")
        self.policy = str(root / "policy")
        self.context = str(root / "ctx")
        self.outputs = str(self.out)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build(self, **kw):
        args = dict(subject_root=self.subject, openspec_root=self.openspec,
                    policy_root=self.policy, context_root=self.context,
                    outputs=self.outputs)
        args.update(kw)
        return invoke.build_request(**args)

    def test_request_is_schema_valid(self):
        """D1's control: the emitted request validates against the frozen
        request contract. The shipped heredoc failed here (3 of 7 fields)."""
        req = self._build()
        errors = schemacheck.validate(req, schemacheck.load("request.schema.json"))
        self.assertEqual(errors, [], f"builder request violates schema: {errors}")

    def test_policy_digest_is_sourced_from_the_signed_binding(self):
        """The authority rule (design.md round-18): `policy.expected_digest`
        is the context's signed claim, never a recompute from policy bytes.
        Binds a context whose digest DIFFERS from the real policy file, so a
        recomputing builder — which would make `policy.resolve`'s identity check
        a tautology — returns the other value and fails here."""
        divergent = "sha256:" + "c" * 64
        fx.build_root(self.tmp / "div", binding=True,
                      binding_expected_digest=divergent)
        req = invoke.build_request(
            subject_root=self.subject, openspec_root=self.openspec,
            policy_root=str(self.tmp / "div" / "policy"),
            context_root=str(self.tmp / "div" / "ctx"),
            outputs=self.outputs)
        ctx = json.loads((self.tmp / "div" / "ctx" / "context.json").read_text())
        self.assertEqual(req["policy"]["expected_digest"],
                         ctx["policy_binding"]["expected_digest"])
        # And it is NOT what a recompute from the policy bytes would claim:
        from hub.coherence import canon
        real_bundle = json.loads((self.tmp / "div" / "policy" / "policy.json").read_text())
        self.assertNotEqual(req["policy"]["expected_digest"],
                            canon.digest_obj("policy/v1", real_bundle))


    def _launch(self):
        reg = load_registry(REGISTRY)
        prof = reg["profiles"][0]
        return invoke.build_launch(
            image=reg["image"], profile=prof["label"],
            manifest_digest=prof["image_manifest_digest"],
            subject_root=self.subject, openspec_root=self.openspec,
            policy_root=self.policy, context_root=self.context)

    def test_launch_passes_validate_with_four_readonly_mounts(self):
        """A containerized run needs FOUR read-only mounts — subject, openspec,
        policy, context — each with a unique target (`_validate_mounts` rejects
        a duplicate or a writable one). The shipped template mounted only the
        subject, so `run_containerized`'s root-rewrite died on
        `unmounted-root:openspec` (round-18 D1's twin)."""
        cfg = self._launch()
        reg = load_registry(REGISTRY)
        ctx = launcher.validate_launch(
            cfg, [p["label"] for p in reg["profiles"]])
        targets = sorted(m["target"] for m in ctx["mounts"])
        self.assertEqual(len(ctx["mounts"]), 4,
                         f"expected four input mounts, got {ctx['mounts']}")
        self.assertEqual(len(targets), len(set(targets)),
                         f"mount targets must be unique: {targets}")
        for m in ctx["mounts"]:
            self.assertTrue(m["readonly"], f"mount not readonly: {m}")

    def test_output_is_never_a_mount_entry(self):
        """/output is the launcher's single writable bind, added by
        `run_containerized`; naming it in `mounts` would either collide or
        hand the container a writable path the isolation profile forbids."""
        cfg = self._launch()
        for m in cfg["mounts"]:
            self.assertNotEqual(m["target"], "/output",
                                "/output must not be declared in mounts")
            self.assertNotEqual(m["target"], "/output/")


    def test_unsigned_context_is_refused(self):
        """The builder must not launder a context the service would refuse into
        a well-formed request. With a control-plane key configured, an unsigned
        context is a ContextError at load; if the builder read context.json
        directly it would emit a valid-looking request over untrusted
        authority. The fixture context is issuer-labeled but unsigned."""
        import os
        from hub.coherence import context as ctx_mod
        with mock.patch.dict(os.environ, {"HUB_COHERENCE_CP_KEY": "a" * 64}):
            with self.assertRaises(ctx_mod.ContextError):
                self._build()

    def test_missing_binding_fails_closed(self):
        """A context with no policy_binding carries no authority claim; the
        builder must refuse rather than fall back to recomputing from policy
        bytes (the tautology the binding rule exists to stop). The refusal
        happens INSIDE context.load — the binding is required by the frozen
        context schema — which is exactly why the builder can index
        policy_binding['expected_digest'] without a guard of its own."""
        from hub.coherence import context as ctx_mod
        fx.build_root(self.tmp / "nobind", binding=False)
        with self.assertRaises(ctx_mod.ContextError) as cm:
            invoke.build_request(
                subject_root=self.subject, openspec_root=self.openspec,
                policy_root=self.policy,
                context_root=str(self.tmp / "nobind" / "ctx"),
                outputs=self.outputs)
        self.assertIn("policy_binding", str(cm.exception))


class BuilderIsUsableByTheDriverTest(unittest.TestCase):
    """The pieces must compose: a builder-produced request and launch config
    must survive the real driver's path (schema validation, launch validation,
    root rewriting, then a mocked container exit 0). This is the check that
    would have caught D1 and D3 in one stroke — the shipped payload never made
    it through `run_containerized` because nothing ran it through there."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dg-invoke-drv-"))
        self.req_path, self.out = fx.build_root(self.tmp, binding=True)
        self.subject = str(self.tmp / "subject")
        self.openspec = str(self.tmp / "openspec")
        self.policy = str(self.tmp / "policy")
        self.context = str(self.tmp / "ctx")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_builder_output_runs_containerized(self):
        from hub.coherence import container_exec as ce
        from hub.coherence.launcher import LaunchRun

        req = invoke.build_request(
            subject_root=self.subject, openspec_root=self.openspec,
            policy_root=self.policy, context_root=self.context,
            outputs=str(self.out))
        reg = load_registry(REGISTRY)
        prof = reg["profiles"][0]
        cfg = invoke.build_launch(
            image=reg["image"], profile=prof["label"],
            manifest_digest=prof["image_manifest_digest"],
            subject_root=self.subject, openspec_root=self.openspec,
            policy_root=self.policy, context_root=self.context)
        rj = self.tmp / "req.json"
        lj = self.tmp / "launch.json"
        rj.write_text(json.dumps(req))
        lj.write_text(json.dumps(cfg))

        def fake_run(ctx, *, output_dir, container_args, env):
            # The driver must have rewritten the four roots to mount targets
            # and replaced outputs with /output — proof the mounts cover them.
            staged = json.loads((Path(output_dir) / "request.container.json").read_text())
            assert staged["subject"]["root"] == "/input"
            assert staged["openspec"]["root"].startswith("/openspec")
            assert staged["policy"]["root"].startswith("/policy")
            assert staged["context"]["root"].startswith("/context")
            assert staged["outputs"] == "/output"
            (Path(output_dir) / "result.json").write_text(
                json.dumps({"decision": "PASS"}))
            return LaunchRun(0, b"", "completed")

        with mock.patch.object(ce.launcher, "run", side_effect=fake_run) as m:
            rc = ce.run_containerized(str(rj), str(lj), str(REGISTRY))
        self.assertEqual(rc, 0, "builder output must run clean through the driver")
        m.assert_called_once()

    def test_uncovered_root_is_rejected_not_run(self):
        """Symmetric control: a launch that drops a mount must make the driver
        refuse (exit 30, `unmounted-root`) rather than launch a container whose
        view of the inputs is missing a root. The builder is what guarantees all
        four roots are covered; this pins that the consequence of NOT covering
        one is a refusal, so a builder regression that dropped a mount could
        never turn into a silently-shorter evaluation."""
        from hub.coherence import container_exec as ce
        req = invoke.build_request(
            subject_root=self.subject, openspec_root=self.openspec,
            policy_root=self.policy, context_root=self.context,
            outputs=str(self.out))
        cfg = invoke.build_launch(
            image="localhost/devgate-coherence", profile="linux-amd64-v1",
            manifest_digest=load_registry(REGISTRY)["profiles"][0]["image_manifest_digest"],
            subject_root=self.subject, openspec_root=self.openspec,
            policy_root=self.policy, context_root=self.context)
        cfg["mounts"] = [m for m in cfg["mounts"] if m["target"] != "/openspec"]
        rj = self.tmp / "r.json"; lj = self.tmp / "l.json"
        rj.write_text(json.dumps(req)); lj.write_text(json.dumps(cfg))
        with mock.patch.object(ce.launcher, "run") as m:
            rc = ce.run_containerized(str(rj), str(lj), str(REGISTRY))
        m.assert_not_called()
        self.assertEqual(rc, 30)


class InvokeAsACommandTest(unittest.TestCase):
    """The CI shell must only RUN a command, not assemble request fields —
    assembling them in bash is a second implementation of the contract (the
    very thing D1 shipped as). So invoke.py is runnable: it takes the roots as
    arguments and writes request.json + launch.json that the driver consumes."""

    def test_writes_request_and_launch_files(self):
        import subprocess
        tmp = Path(tempfile.mkdtemp(prefix="dg-invoke-cli-"))
        try:
            fx.build_root(tmp, binding=True)
            req_p = tmp / "request.json"
            launch_p = tmp / "launch.json"
            reg = load_registry(REGISTRY)
            prof = reg["profiles"][0]
            proc = subprocess.run(
                [sys.executable, "-m", "hub.coherence.invoke",
                 "--subject", str(tmp / "subject"),
                 "--openspec", str(tmp / "openspec"),
                 "--policy", str(tmp / "policy"),
                 "--context", str(tmp / "ctx"),
                 "--outputs", str(tmp / "out"),
                 "--image", reg["image"], "--profile", prof["label"],
                 "--manifest-digest", prof["image_manifest_digest"],
                 "--request-out", str(req_p), "--launch-out", str(launch_p)],
                cwd=str(REPO), capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0,
                             f"builder CLI failed: {proc.stderr}")
            req = json.loads(req_p.read_text())
            cfg = json.loads(launch_p.read_text())
            self.assertEqual(
                schemacheck.validate(req, schemacheck.load("request.schema.json")),
                [], "CLI-emitted request must be schema-valid")
            self.assertEqual(len(cfg["mounts"]), 4)
            self.assertNotIn("/output", [m["target"] for m in cfg["mounts"]])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
