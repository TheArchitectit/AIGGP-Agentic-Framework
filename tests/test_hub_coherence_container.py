# // spec: coh-rt-01, coh-rt-02, coh-rt-05, coh-rt-07, coh-id-04, coh-dec-04
"""Container increment suite: digest-pinned Containerfile (coh-rt-01),
base-image pinning (coh-rt-02), the containerized-execution driver's exit-code
mapping (coh-rt-05, coh-rt-07, coh-dec-04), and the real-container run under
the launcher's enforced flag set. All fixtures synthetic (R9).

Which bytes get launched — the identity registry, the pin's fetchability, and
the smoke run itself — lives in test_coherence_image_identity.py; this file
covers HOW the driver launches them.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import container_exec as ce
from hub.coherence import schemacheck
from hub.coherence.launcher import LaunchRun
from hub.coherence.profiles import load_registry, resolve_profile
from tests.test_coherence_image_identity import ensure_pinned_image  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CONTAINERFILE = REPO / "container/Containerfile"
REGISTRY = REPO / "container/execution-profiles.json"


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

    def test_build_context_excludes_untracked_bytecode(self):
        """The build context must be tracked source only.

        Measured 2026-09-23: `COPY hub/` from a working tree carried 33
        untracked, gitignored `__pycache__` entries into the image, so
        rebuilding the SAME source locally and from a clean checkout produced
        different bytes (config digests 8ca8ac95… vs ef02f38a…). The recorded
        identity was then unreproducible by anyone — and `.gitignore` does not
        cover a build context. `.containerignore` is what keeps the two in
        step; with it the dirty-tree build reproduces ef02f38a… exactly.
        """
        ignore = REPO / ".containerignore"
        self.assertTrue(
            ignore.exists(),
            "no .containerignore: untracked bytecode rides into the image, "
            "so the pinned identity is unreproducible")
        patterns = {ln.strip() for ln in
                    ignore.read_text(encoding="utf-8").splitlines()}
        self.assertIn("**/__pycache__", patterns,
                      "bytecode must be excluded from the build context")

    def test_containerfile_carries_the_frozen_schemas(self):
        """coh-rt-08, and the podman-free control for the F1/D2 regression.

        `COPY hub/` alone does not ship the contracts: schemacheck.SCHEMA_DIR
        resolves to <repo>/openspec/changes/devgate-spec-coherence-service/
        schemas, which lives OUTSIDE hub/. So `run()` inside the container dies
        on FileNotFoundError loading its own request.schema.json (round-18 D2).
        The CI job that holds this line self-skips on runners without podman, so
        the guard would be inert exactly where the regression lives — this unit
        always executes, so the regression is caught on any runner.

        The expected destination is DERIVED from the runtime's own path
        expression, not hardcoded: if the repo location or the Containerfile's
        WORKDIR move, the assertion tracks them instead of freezing a string
        that quietly stops matching reality."""
        import re
        from hub.coherence import schemacheck
        workdir = re.search(r"^WORKDIR\s+(\S+)", self.text, re.M)
        self.assertIsNotNone(workdir, "Containerfile must set a WORKDIR")
        wd = workdir.group(1)
        # schemacheck.py ships at <wd>/hub/coherence/schemacheck.py (COPY hub/),
        # so SCHEMA_DIR — the module's parent.parent.parent plus the package
        # path — resolves to this in-container location. A COPY whose
        # destination equals it puts the schemas where load() looks.
        in_container_dir = (f"{wd}/"
                            + schemacheck.SCHEMA_DIR.relative_to(REPO).as_posix())
        # Resolve every COPY destination to an in-container absolute path, the
        # way the build engine does: a `./x` or bare `x` target is relative to
        # WORKDIR; a leading-`/` target is already absolute. Trailing slash is
        # cosmetic (COPY lands the source's contents at the dir either way).
        def resolve(dest):
            dest = dest.rstrip("/")
            if dest.startswith("/"):
                return dest
            return (wd.rstrip("/") + "/" + dest.lstrip("./")).rstrip("/")
        copies = [c for c in _lines(self.text, "COPY ") if "->" not in c]
        dests = [resolve(c.split()[-1]) for c in copies]
        self.assertIn(
            in_container_dir, dests,
            f"Containerfile must COPY the schema dir to {in_container_dir} "
            f"(where schemacheck.SCHEMA_DIR resolves in-container); COPY "
            f"destinations found: {dests}")
        self.assertEqual(
            sum(1 for d in dests if d == in_container_dir), 1,
            f"schema dir must be COPYed exactly once; got {dests}")
        # And it must be a directory-copy of the source schemas, not a single
        # file — the whole frozen set has to be present for load() of any name.
        src = next(c.split()[1] for c in copies
                   if resolve(c.split()[-1]) == in_container_dir)
        self.assertTrue(src.rstrip("/").endswith("schemas"),
                        f"schema COPY source must be the schemas dir, got {src}")


DRIVER_API = "devgate.spec-coherence/v1"


def launch_cfg(manifest=None):
    """Launch config whose profile/digest resolve against the real registry.

    The image comes FROM the registry too: a launch is only coherent when the
    ref addresses the recorded bytes, and a hardcoded localhost tag let this
    fixture drift from the pin the whole contract is about.
    """
    reg = load_registry(REGISTRY)
    dig = resolve_profile(reg, "linux-amd64-v1")["image_manifest_digest"]
    mdig = manifest or dig
    return {
        "image": f"{reg['image']}@{mdig}",
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
        "profile": "linux-amd64-v1",
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
        p.write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8")
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
                return json.loads(p.read_text(encoding="utf-8"))
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

    def test_ref_digest_mismatch_with_declared_pin_rejected(self):
        # Round-8 spec audit (coh-rt-01/coh-id-04): the registry pin binds the
        # EXECUTED ref, not just the declared manifest field — declaring the
        # pinned digest while pointing the ref at other bytes must not run.
        cfg = launch_cfg()
        cfg["image"] = "localhost/devgate-coherence@sha256:" + "e" * 64
        rc, m = self._run(driver_request(), cfg)
        self.assertEqual(rc, 30)
        self.assertIn("image-ref-digest-mismatch",
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

        def fake_run(ctx, *, output_dir, container_args, env=None):
            captured["args"] = container_args
            # The driver stages the rewritten request inside the output
            # directory itself, so in-container envelopes (emitted beside the
            # request file) land on the designated output bind.
            captured["staged"] = json.loads(
                (Path(output_dir) / ce.STAGED_REQUEST_NAME).read_text(encoding="utf-8"))
            (output_dir / "result.json").write_text('{"decision": "PASS"}', encoding="utf-8")
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
        def fake_run(ctx, *, output_dir, container_args, env=None):
            (output_dir / "result.json").write_text('{"decision": "FAIL"}', encoding="utf-8")
            return LaunchRun(20, b"", "completed")

        rc, _ = self._run(driver_request(), launch_cfg(), fake_run)
        self.assertEqual(rc, 20)

    def test_coherent_execution_error_relayed(self):
        # A completed container exiting 32 with an agreeing ERROR envelope
        # (e.g. an in-container evaluator crash) relays untouched.
        def fake_run(ctx, *, output_dir, container_args, env=None):
            (output_dir / "result.json").write_text(json.dumps({
                "decision": "ERROR",
                "error": {"class": "execution",
                          "reason": "evaluator-crash:KeyError:crasher",
                          "stage": "evaluation"}}), encoding="utf-8")
            return LaunchRun(32, b"", "completed")

        rc, _ = self._run(driver_request(), launch_cfg(), fake_run)
        self.assertEqual(rc, 32)

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
            env = json.loads((Path(outs) / "result.json").read_text(encoding="utf-8"))
            self.assertIn("outputs-inside-mount-source",
                          env["error"]["reason"])
            m.assert_not_called()

    def test_contradictory_error_field_is_error(self):
        # Round-7 finding 3 (coh-dec-01): exit 0 with decision PASS but a
        # non-null error field is an exit/result disagreement — never
        # relayed as the permissive signal.
        def fake_run(ctx, *, output_dir, container_args, env=None):
            (output_dir / "result.json").write_text(
                json.dumps({"decision": "PASS",
                           "error": {"class": "execution", "reason": "hidden",
                                     "stage": "evaluation"}}), encoding="utf-8")
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

        def fake_run(ctx, *, output_dir, container_args, env=None):
            (output_dir / "result.json").write_text('{"decision": "PASS"}', encoding="utf-8")
            return LaunchRun(0, b"", "completed")

        with mock.patch.object(ce.result, "emit", side_effect=spy):
            rc, _ = self._run(driver_request(), launch_cfg(), fake_run)
        self.assertEqual(rc, 0)
        self.assertIn(ce.STAGED_REQUEST_NAME, emitted)

    # --- coh-int-05: adapter default-deny (ERROR, never neutral/pass) ---

    def test_timeout_surfaces_error_not_pass(self):
        """coh-int-05: a container that times out MUST produce ERROR/32,
        never a neutral or passing verdict."""
        rc, _ = self._run(driver_request(), launch_cfg(),
                          lambda *a, **kw: LaunchRun(0, b"", "timeout"))
        self.assertEqual(rc, 32)
        env = self._envelope()
        self.assertEqual(env["decision"], "ERROR")
        self.assertEqual(env["error"]["class"], "execution")
        self.assertIn("launch-timeout", env["error"]["reason"])
        # Must NOT read as PASS or ADVISORY
        self.assertNotIn(env["decision"], ("PASS", "ADVISORY", "FAIL"))

    def test_unparseable_result_is_error_not_pass(self):
        """coh-int-05: a result.json that cannot be parsed (truncated,
        corrupted, or malformed JSON) MUST surface ERROR/32 — never a
        default-allow or neutral verdict."""
        def fake_run(ctx, *, output_dir, container_args, env=None):
            # Write garbage that is not valid JSON
            (output_dir / "result.json").write_text("{broken json!!!", encoding="utf-8")
            return LaunchRun(0, b"", "completed")

        rc, _ = self._run(driver_request(), launch_cfg(), fake_run)
        self.assertEqual(rc, 32)
        env = self._envelope()
        self.assertEqual(env["decision"], "ERROR")
        self.assertEqual(env["error"]["class"], "execution")
        self.assertIn("exit-code contract", env["error"]["reason"])
        self.assertNotIn(env["decision"], ("PASS", "ADVISORY"))

    def test_no_result_file_is_error_not_pass(self):
        """coh-int-05: when the container produces no result.json at all
        (e.g. it was killed before writing, or the output bind vanished),
        the adapter MUST surface ERROR/32 — never absence-as-pass."""
        def fake_run(ctx, *, output_dir, container_args, env=None):
            # Container exited but wrote nothing
            return LaunchRun(0, b"", "completed")

        rc, _ = self._run(driver_request(), launch_cfg(), fake_run)
        self.assertEqual(rc, 32)
        env = self._envelope()
        self.assertEqual(env["decision"], "ERROR")
        self.assertEqual(env["error"]["class"], "execution")
        self.assertIn("exit-code contract", env["error"]["reason"])
        # Absence must never read as PASS
        self.assertNotEqual(env["decision"], "PASS")

    def test_zero_assertion_aggregates_to_pass(self):
        """Known aggregation hole: a zero-assertion run produces an
        empty ledger with no findings. result.decide() with an empty
        ledger and no error_class falls through to ("PASS", EXIT_PASS).
        This is the coh-int-05 aggregation hole: a gate that could not
        evaluate (zero assertions to evaluate) can aggregate to a clean
        PASS. Reported as a carry-forward to the AIGGP package — NOT
        redesigned here. The test asserts the current behavior so the
        hole is visible and cannot silently disappear."""
        from hub.coherence import result
        decision, code = result.decide([], stage=1)
        self.assertEqual(decision, "PASS")
        self.assertEqual(code, result.EXIT_PASS)
        # The hole: empty ledger = clean pass. This is NOT an ERROR.
        # A gate with nothing to evaluate should arguably be UNRESOLVED,
        # but current code returns PASS. Reported, not fixed.


@unittest.skipUnless(shutil.which("podman"), "podman not available")
class TestContainerExecReal(unittest.TestCase):
    """End-to-end against the real pinned image: an in-container honest
    rejection must relay through the exit-code agreement check as exit 30."""

    def setUp(self):
        ensure_pinned_image(self)
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
        rp.write_text(json.dumps(req), encoding="utf-8")
        cfg = launch_cfg()
        cfg["mounts"] = []
        cp = self.tmp / "launch.json"
        cp.write_text(json.dumps(cfg), encoding="utf-8")
        rc = ce.run_containerized(str(rp), str(cp), str(REGISTRY))
        res = json.loads((self.out / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(rc, 30, res)
        self.assertEqual(res["decision"], "ERROR")


if __name__ == "__main__":
    unittest.main()
