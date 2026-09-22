# // spec: coh-int-01, coh-int-05
"""Local developer command (scripts/coherence-local) vs the CI template.

coh-int-01's byte-equivalence promise has two halves: the CI invocation
(template) and the local command must produce *the same bytes* for the same
inputs. What this suite pins for coh-int-05 is narrower than the requirement's
whole surface — no adapter may reinterpret or downgrade a canonical decision:
the wrapper is checked to relay the service's exit verbatim and to surface a
builder refusal as ERROR-class 30, never default-allow green. The
requirement's timeout scenario belongs to the service/driver, already tested
in the exit-code sweep; nothing here re-pins it. The builder (hub/coherence/invoke.py) is already one implementation
shared by both — this suite pins the SHELL half: that the local wrapper's
actual emitted request.json / launch.json are byte-identical to what the
template's own command, replayed verbatim, emits.

Why "replayed verbatim" and not a copy: round-18 D1 was a CI heredoc drifting
from the contract while a text-matching test watched. A test that hand-copied
the template's command lines would be a third implementation of the same
invocation and could drift from BOTH. So the builder command is extracted from
the template file at test time — if the template changes its flags, the replay
changes too, and any wrapper that did not follow fails here. That is what
makes every byte comparison killable rather than decorative.

Real container execution of the driver step is deliberately NOT asserted as
equivalent: it requires the image to match the identity registry (publish-gated
re-pin, tasks.md round-18). What this suite DOES pin, including that step: the
wrapper's two subprocess commands are the template's two commands, same flags,
same order — verified from the wrapper's --dry-run transcript against the
template-extracted command forms.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO = Path(__file__).resolve().parent.parent
WRAPPER = REPO / "scripts" / "coherence-local"
TEMPLATE = REPO / "templates" / "github-workflows" / "spec-coherence.yml"

from tests.fixtures.coherence import fixtures as fx  # noqa: E402


def _template_blocks() -> str:
    """Concatenation of the template's `run: |` bodies, de-indented — the same
    extraction tests/test_coherence_workflow_template.py uses, so a template
    edit that breaks THIS view of the file breaks that suite too."""
    lines = (TEMPLATE.read_text()).split("\n")
    out, i = [], 0
    while i < len(lines):
        m = re.match(r"^(\s*)run: \|$", lines[i])
        if m:
            ind = len(m.group(1))
            j = i + 1
            while j < len(lines) and (not lines[j].strip()
                                      or len(lines[j]) - len(lines[j].lstrip()) > ind):
                out.append(lines[j][ind + 2:] if len(lines[j]) > ind + 2 else "")
                j += 1
            i = j
        else:
            i += 1
    return "\n".join(out)


# Find a module invocation inside the template, from its `-m <module> \` head
# to the closing `)` of its `( ... )` subshell, and return argv with the flag
# VALUES exactly as the template spells them (quoted strings unwrapped, $VARS
# kept literal so callers substitute). One extraction helper for both commands:
# two copies would themselves be the drift this suite hunts.
def _extract_template_command(module: str) -> list[str]:
    body = _template_blocks()
    m = re.search(rf"python3 -m {re.escape(module)} \\\n(.*?)\)(?:\s|\\|$)",
                  body, re.S)
    assert m, (f"could not extract the `-m {module}` invocation from the "
               "template — its command shape changed; this suite must be "
               "re-read, not skipped")
    block = m.group(1)
    argv = ["python3", "-m", module]
    for flag, value in re.findall(r'--(\S+)\s+"([^"]*)"', block):
        argv.extend((f"--{flag}", value))
    return argv


def _template_builder_command() -> list[str]:
    return _extract_template_command("hub.coherence.invoke")


def _template_driver_command() -> list[str]:
    return _extract_template_command("hub.coherence")


class WrapperExistsTest(unittest.TestCase):
    def test_wrapper_exists_and_executable(self):
        self.assertTrue(WRAPPER.is_file(),
                        f"missing local command: {WRAPPER} (coh-int-01's "
                        "local half — the CI template has no documented local "
                        "equivalent to pin against)")
        self.assertTrue(os.access(WRAPPER, os.X_OK),
                        "scripts/coherence-local must be executable")

    def test_wrapper_shells_only_the_pinned_modules(self):
        """The service is stdlib-only by contract and the invocation is pinned
        by identity (the template's DEVGATE_PIN): the wrapper may only shell out
        to `python3 -m hub.coherence[.invoke]`, never install anything. A pip
        line would make 'local == CI' depend on what the developer installed."""
        text = WRAPPER.read_text()
        self.assertNotIn("pip install", text,
                         "wrapper installs packages — breaks stdlib-only local use")
        # Every "python3" token literal is a `-m` module invocation, and every
        # such invocation names hub.coherence or hub.coherence.invoke (the two
        # commands the template runs — nothing else, not a vendored script).
        invocations = re.findall(r'"python3", "-m", "([^"]+)"', text)
        self.assertEqual(len(invocations), 2,
                         f"expected exactly the builder + driver invocations, "
                         f"found {invocations} (plus any unquoted uses)")
        for mod in invocations:
            self.assertIn(mod, ("hub.coherence", "hub.coherence.invoke"),
                          f"wrapper invokes a module the template does not: {mod}")


class BuilderByteEquivalenceTest(unittest.TestCase):
    """The load-bearing case: same input roots, two invocations — the template's
    own command replayed, and the wrapper — must emit byte-identical
    request.json and launch.json. Byte-identical also pins key order and
    separators: 'byte-equivalent results', not 'equivalent in spirit'."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dg-local-"))
        fx.build_root(self.tmp, binding=True)
        self.roots = {
            "subject": self.tmp / "subject",
            "openspec": self.tmp / "openspec",
            "policy": self.tmp / "policy",
            "context": self.tmp / "ctx",
        }

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run_template_command(self, out_dir: Path) -> None:
        argv = _template_builder_command()
        # The template's shell variables, substituted with what the template's
        # own env would hold for these inputs. DIGEST/IMAGE/PROFILE come from
        # the pinned registry — the same source the template reads (its
        # digest-resolution step loads execution-profiles.json), so a wrapper
        # consulting anything else cannot byte-match.
        reg = json.loads((REPO / "container/execution-profiles.json").read_text())
        prof = reg["profiles"][0]
        subs = {
            "$CAND_ROOT": str(self.tmp),        # template: CAND_ROOT="$PWD"
            "$SUBJECT": "subject",              # template: a COHERENCE_SUBJECTS entry
            "$COHERENCE_OPENSPEC_ROOT": str(self.roots["openspec"]),
            "$COHERENCE_POLICY_ROOT": str(self.roots["policy"]),
            "$COHERENCE_CONTEXT_ROOT": str(self.roots["context"]),
            "$OUT": str(out_dir),
            "$COHERENCE_IMAGE": reg["image"],
            "$COHERENCE_PROFILE": prof["label"],
            "$DIGEST": prof["image_manifest_digest"],
        }
        cmd = []
        for a in argv:
            for k, v in subs.items():
                a = a.replace(k, v)
            cmd.append(a)
        env = dict(os.environ, PYTHONPATH=".")
        r = subprocess.run(cmd, cwd=str(REPO), env=env,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, f"template replay failed: {r.stderr}")

    def _run_wrapper(self, out_dir: Path, extra=()) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(WRAPPER), "--subject", str(self.roots["subject"]),
             "--openspec", str(self.roots["openspec"]),
             "--policy", str(self.roots["policy"]),
             "--context", str(self.roots["context"]),
             "--outputs", str(out_dir), "--build-only", *extra],
            capture_output=True, text=True)

    def test_request_and_launch_bytes_match_the_template_replay(self):
        # `outputs` is part of the request, so the two runs cannot share one
        # directory (each would overwrite the other). Byte-equivalence is
        # therefore checked with the outputs field normalized to its own
        # directory — everything else, byte for byte, including key order.
        out_a, out_b = self.tmp / "oa", self.tmp / "ob"
        for d in (out_a, out_b):
            d.mkdir()
        self._run_template_command(out_a)
        w = self._run_wrapper(out_b)
        self.assertEqual(w.returncode, 0, f"wrapper failed: {w.stderr}")

        def normalize(path: Path, own_out: Path) -> bytes:
            b = path.read_bytes()
            self.assertTrue(b, f"empty {path.name} — a byte compare of "
                               "nothing proves nothing")
            return b.replace(str(own_out).encode(), b"<OUT>")

        for name in ("request.json", "launch.json"):
            tb = normalize(out_a / name, out_a)
            wb = normalize(out_b / name, out_b)
            self.assertEqual(
                tb, wb,
                f"{name} differs between the template's own command and the "
                "local wrapper (coh-int-01 byte-equivalence): "
                f"template={tb[:280]!r} wrapper={wb[:280]!r}")

    def test_wrapper_surfaces_builder_refusal_non_green(self):
        """Fail-closed parity: the template marks a builder refusal FAIL with
        the build log; the local command must surface the same refusal as a
        non-green exit, not swallow it. A context with no policy_binding is the
        designed refusal (context schema makes the binding required)."""
        bad = self.tmp / "nobinding"
        fx.build_root(bad, binding=False)
        out = self.tmp / "outfail"
        out.mkdir()
        w = self._run_wrapper(out, extra=(
            "--openspec", str(bad / "openspec"),
            "--policy", str(bad / "policy"),
            "--context", str(bad / "ctx")))
        self.assertEqual(w.returncode, 30,
                         "a refused context is invalid input — exit 30 per the "
                         "frozen contract (coh-dec-04), same class the service "
                         "itself maps refusals to; neither the builder's raw 1 "
                         "nor a swallowed green")
        self.assertIn("policy_binding", w.stderr + w.stdout,
                      "the refusal must name its cause, as the template's "
                      "build.log does")

    def test_unsigned_context_refused_locally_under_a_configured_cp_key(self):
        """`local == CI` must hold in the signature cases, not just the happy
        path. context.load refuses an unsigned context whenever
        HUB_COHERENCE_CP_KEY is set (context.py:75); if the wrapper ran its
        children with a stripped environment, the key would not reach them and
        the exact context CI rejects would build a request locally — a
        silent divergence byte-equivalence alone cannot see, because both
        stripped-env runs would agree with each other. The wrapper's env line
        is the behavior under test: propagation exits 30 naming the cause."""
        bad = self.tmp / "cpkey"
        fx.build_root(bad, binding=True)  # signed-issuer fixture, unsigned ctx
        out = self.tmp / "outcp"
        out.mkdir()
        r = subprocess.run(
            [str(WRAPPER), "--subject", str(bad / "subject"),
             "--openspec", str(bad / "openspec"),
             "--policy", str(bad / "policy"),
             "--context", str(bad / "ctx"),
             "--outputs", str(out), "--build-only"],
            capture_output=True, text=True,
            env={**os.environ, "HUB_COHERENCE_CP_KEY": "a" * 64})
        self.assertEqual(r.returncode, 30,
                         f"with a control-plane key configured the unsigned "
                         f"context must be refused (exit 30), got "
                         f"{r.returncode} — if this passes green, the wrapper "
                         f"did not propagate the key to its children")
        self.assertIn("unsigned", r.stderr + r.stdout,
                      "the refusal must name the control-plane-key cause")

    def test_outputs_dir_is_created_not_presupposed(self):
        """Developers point --outputs at a fresh run directory; the template
        mkdirs $OUT the same way. Without this, dropping the wrapper's mkdir
        is a silent local-only crash no other test (all of which pre-create
        their dirs) would catch."""
        out = self.tmp / "fresh" / "nested" / "run1"
        w = self._run_wrapper(out)
        self.assertEqual(w.returncode, 0,
                         f"a nonexistent outputs dir must be created, not "
                         f"crash: {w.stderr}")
        self.assertTrue((out / "request.json").is_file())

    def test_unknown_profile_label_refused_not_fallback(self):
        """Asking for a profile the identity registry does not contain must
        fail loudly: silently running the registry's *first* profile instead
        would execute bytes the CI pin does not name, under a command that
        claimed otherwise — the divergence the whole registry lookup exists
        to prevent."""
        out = self.tmp / "outprof"
        w = self._run_wrapper(out, extra=("--profile", "linux-riscv-v9"))
        self.assertNotEqual(w.returncode, 0,
                            "an absent profile label must not fall back")
        self.assertIn("linux-riscv-v9", w.stderr + w.stdout,
                      "the refusal must name the requested label")


class DryRunTranscriptTest(unittest.TestCase):
    """--dry-run must print EXACTLY the template's two commands (module path,
    flag set, flag order), with the real substituted values. This pins the
    driver step's command form — the part that cannot be byte-compared without
    the publish-gated image — without pretending to execute it."""

    def test_dry_run_prints_the_templates_two_commands(self):
        tmp = Path(tempfile.mkdtemp(prefix="dg-dry-"))
        try:
            fx.build_root(tmp, binding=True)
            out = tmp / "out"
            r = subprocess.run(
                [str(WRAPPER), "--subject", str(tmp / "subject"),
                 "--openspec", str(tmp / "openspec"),
                 "--policy", str(tmp / "policy"),
                 "--context", str(tmp / "ctx"),
                 "--outputs", str(out), "--dry-run"],
                capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            b_flags = [a for a in _template_builder_command() if a.startswith("--")]
            d_flags = [a for a in _template_driver_command() if a.startswith("--")]
            lines = [ln for ln in r.stdout.splitlines() if ln.startswith("$ ")]
            self.assertGreaterEqual(len(lines), 2,
                                    f"expected >=2 '$ ' command lines, got: {r.stdout!r}")
            b_line, d_line = lines[0][2:].split(), lines[1][2:].split()
            # Same flag SEQUENCE as the template's own commands.
            self.assertEqual([a for a in b_line if a.startswith("--")], b_flags,
                             "wrapper's builder command diverges from the "
                             "template's extracted one (flags/order)")
            self.assertEqual([a for a in d_line if a.startswith("--")], d_flags,
                             "wrapper's driver command diverges from the "
                             "template's extracted one (flags/order)")
            # The driver consumes the files the builder just wrote.
            self.assertIn(str(out / "request.json"), " ".join(d_line))
            self.assertIn(str(out / "launch.json"), " ".join(d_line))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class ProfileIdentityTest(unittest.TestCase):
    """Identity parity: the template's digest step resolves the digest from
    the registry by ITS label and fails closed on disagreement
    (spec-coherence.yml:210-221). The wrapper must have the same semantics —
    a registry head-insert, a pin edit, or a drifted test-substitute all
    silently diverge local from CI otherwise. The real template pins
    linux-amd64-v1, so all drift cases run under --profile: a registry whose
    pinned-label entry no longer matches the template's pin fails the
    DEFAULT identity too — that IS the honest refusal, and the override path
    is where the distinction is observable."""

    def _wrapper(self, out: Path, tmp: Path, env_extra: dict,
                 extra=()) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(WRAPPER), "--subject", str(tmp / "subject"),
             "--openspec", str(tmp / "openspec"),
             "--policy", str(tmp / "policy"),
             "--context", str(tmp / "ctx"),
             "--outputs", str(out), "--build-only", *extra],
            capture_output=True, text=True,
            env={**os.environ, **env_extra})

    def test_head_inserted_registry_profile_does_not_become_default(self):
        """A new profile at the head of the registry must not silently become
        'the' local identity while CI still pins the old label — the
        fallback-to-first-entry this design replaced would have built a
        request for different bytes than CI with no signal at all. Asserted
        on the emitted request/launch: the CI-pinned digest must be the one
        that went in."""
        tmp = Path(tempfile.mkdtemp(prefix="dg-prof-"))
        try:
            fx.build_root(tmp, binding=True)
            real = json.loads((REPO / "container/execution-profiles.json").read_text())
            ci_digest = real["profiles"][0]["image_manifest_digest"]
            real["profiles"].insert(0, {
                "label": "znew-v9", "platform": "linux/z",
                "image_manifest_digest": "sha256:" + "d" * 64,
                "base_image": "example@sha256:" + "e" * 64,
                "semantic_equivalence_group": "default", "built": "2099-01-01"})
            prof_file = tmp / "profiles.json"
            prof_file.write_text(json.dumps(real))
            out = tmp / "out"
            w = self._wrapper(out, tmp,
                              {"DEVGATE_EXECUTION_PROFILES": str(prof_file)})
            self.assertEqual(w.returncode, 0,
                             f"the CI-pinned profile is still in the registry "
                             f"(just not first) — the default identity must "
                             f"still resolve to it: {w.stderr}")
            launch = (out / "launch.json").read_text()
            self.assertIn(ci_digest, launch,
                          "launch config does not name the CI-pinned digest")
            self.assertNotIn("znew-v9", launch,
                             "head-inserted profile hijacked the local "
                             "identity — local ran bytes CI never pinned")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_pinned_digest_not_in_registry_fails_closed(self):
        """CI refuses to run when its pinned digest is absent from the
        registry; so must the local command — under the DEFAULT identity, so
        the template's own label/digest pair is what's checked."""
        tmp = Path(tempfile.mkdtemp(prefix="dg-prof-"))
        try:
            fx.build_root(tmp, binding=True)
            reg = json.loads((REPO / "container/execution-profiles.json").read_text())
            for p in reg["profiles"]:
                p["image_manifest_digest"] = "sha256:" + "f" * 64
            prof_file = tmp / "profiles.json"
            prof_file.write_text(json.dumps(reg))
            out = tmp / "out"
            w = self._wrapper(out, tmp, {"DEVGATE_EXECUTION_PROFILES":
                                         str(prof_file)})
            self.assertNotEqual(w.returncode, 0,
                                "registry drifted off the template's pin — "
                                "a green local run here executes bytes CI "
                                "excludes")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_explicit_override_other_label_warns_and_runs(self):
        """--profile naming a label the template does NOT pin is a deliberate
        opt-out from CI-identity parity (e.g. a future arm64 profile built by
        another job): the template's single pinned digest must not be
        compared against it (that would make the flag dead — no other label
        can match one pin), but running bytes CI never pinned must be said
        out loud, on stderr, and the emitted launch config must carry the
        registry's digest for the requested label."""
        tmp = Path(tempfile.mkdtemp(prefix="dg-prof-"))
        try:
            fx.build_root(tmp, binding=True)
            real = json.loads((REPO / "container/execution-profiles.json").read_text())
            other = dict(real["profiles"][0], label="linux-arm64-v9",
                         image_manifest_digest="sha256:" + "a" * 64,
                         platform="linux/arm64")
            real["profiles"].append(other)
            prof_file = tmp / "profiles.json"
            prof_file.write_text(json.dumps(real))
            out = tmp / "out"
            w = self._wrapper(out, tmp,
                              {"DEVGATE_EXECUTION_PROFILES": str(prof_file)},
                              extra=("--profile", "linux-arm64-v9"))
            self.assertEqual(w.returncode, 0,
                             f"an explicit override must run (warn, not "
                             f"refuse — the refusal path for a disagreement "
                             f"on the template's OWN label is tested "
                             f"elsewhere): {w.stderr}")
            self.assertIn("no comparable ci pin", w.stderr.lower(),
                          "running bytes CI never pinned must be announced, "
                          "not silent")
            self.assertIn("sha256:" + "a" * 64, (out / "launch.json").read_text())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_explicit_profile_pin_conflict_fails_closed(self):
        """--profile naming the SAME label the template pins, with a
        conflicting env digest — the disagreement must refuse, not prefer
        the env silently."""
        tmp = Path(tempfile.mkdtemp(prefix="dg-prof-"))
        try:
            fx.build_root(tmp, binding=True)
            out = tmp / "out"
            w = self._wrapper(out, tmp,
                              {"COHERENCE_IMAGE_MANIFEST_DIGEST":
                               "sha256:" + "1" * 64},
                              extra=("--profile", "linux-amd64-v1"))
            self.assertNotEqual(w.returncode, 0,
                                "explicit pin conflict must fail closed")
            self.assertIn("disagree", w.stderr + w.stdout.lower(),
                          "the refusal must name the registry-vs-pin conflict")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class DriverExitRelayTest(unittest.TestCase):
    """The wrapper's final line is `return subprocess.run(driver…).returncode`.
    A driver run FAILs (exit 20) and a clean PASS exits 0; the service already
    maps every container outcome onto the frozen contract (coh-dec-04), so the
    wrapper's only job is relaying the number unchanged — a `return 0` there,
    or any re-mapping, turns real failures green locally.

    Runs the wrapper's own commands with `python3` resolved to a stub that
    plays the service (builder succeeds, driver exits 20), so the relay is
    observed without the publish-gated image. The driver command is taken from
    the wrapper's --dry-run transcript, so this tests the same argv the
    real run uses — not a copy the test invented.

    The stub passes ANY non-service invocation through to the real
    interpreter. Without that, the wrapper's own shebang (`env python3`) hits
    the stub and the stub's exit-20 fires for the wrapper itself — the first
    version of this test passed that way, vacuously: both driver mutants
    (return-0, stripped env) survived because the wrapper never ran. The
    driver's environment is dumped so propagation is asserted on the driver
    too, not just the builder."""

    def test_service_exit_20_is_relayed_not_resolved_green(self):
        tmp = Path(tempfile.mkdtemp(prefix="dg-relay-"))
        try:
            fx.build_root(tmp, binding=True)
            out = tmp / "out"
            dry = subprocess.run(
                [str(WRAPPER), "--subject", str(tmp / "subject"),
                 "--openspec", str(tmp / "openspec"),
                 "--policy", str(tmp / "policy"),
                 "--context", str(tmp / "ctx"),
                 "--outputs", str(out), "--dry-run"],
                capture_output=True, text=True)
            self.assertEqual(dry.returncode, 0, dry.stderr)
            lines = [ln[2:] for ln in dry.stdout.splitlines()
                     if ln.startswith("$ ")]
            self.assertEqual(len(lines), 2)

            fake = tmp / "bin"
            fake.mkdir()
            dump = tmp / "driver-env.txt"
            (fake / "python3").write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"$*\" == *hub.coherence.invoke* ]]; then\n"
                '  for a in "$@"; do case "$a" in */request.json|*/launch.json) '
                "echo '{}' > \"$a\";; esac; done\n"
                "  exit 0\n"
                "fi\n"
                'if [[ "$*" == *"-m hub.coherence "* ]]; then\n'
                '  env > "$DRIVER_ENV_DUMP"\n'
                "  exit 20\n"
                "fi\n"
                f'exec {sys.executable} "$@"\n')
            os.chmod(fake / "python3", 0o755)
            r = subprocess.run(
                [str(WRAPPER)] + [a for a in
                                  # rebuild real args; same roots as dry-run
                                  ["--subject", str(tmp / "subject"),
                                   "--openspec", str(tmp / "openspec"),
                                   "--policy", str(tmp / "policy"),
                                   "--context", str(tmp / "ctx"),
                                   "--outputs", str(out)]],
                capture_output=True, text=True,
                env={**os.environ,
                     "PATH": f"{fake}{os.pathsep}{os.environ['PATH']}",
                     "DRIVER_ENV_DUMP": str(dump),
                     "HUB_COHERENCE_CP_KEY": "b" * 64})
            self.assertEqual(r.returncode, 20,
                             f"a FAIL verdict must exit exactly 20 (the frozen "
                             f"contract's FAIL class); wrapper relayed "
                             f"{r.returncode} (stdout={r.stdout!r} "
                             f"stderr={r.stderr!r})")
            # The env the driver actually ran with — a driver-side env strip
            # leaves the relay green and the divergence invisible.
            self.assertTrue(dump.is_file(),
                            "the driver was never invoked as a child of the "
                            "wrapper (or crashed before its env was dumped)")
            denv = dump.read_text()
            self.assertIn("HUB_COHERENCE_CP_KEY=" + "b" * 64, denv,
                          "driver child lost the caller's environment — "
                          "local signature enforcement diverges from CI")
            self.assertIn("PYTHONPATH=.", denv,
                          "driver child lost PYTHONPATH — -m hub.coherence "
                          "cannot resolve from the repo root")
            # The transcript's driver command is what was executed — pin that
            # the argv we just exercised matches it (same flags, in order).
            driver_argv = lines[1].split()
            self.assertEqual(driver_argv[:5],
                             ["python3", "-m", "hub.coherence",
                              "--request", str(out / "request.json")],
                             "the executed driver command diverged from the "
                             "transcript the --dry-run promised")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class ControlPlaneRootsTest(unittest.TestCase):
    def test_missing_roots_fail_loud_not_invented(self):
        """The template SKIPS rather than fabricating control-plane roots; the
        local command must refuse too — a wrapper that defaulted
        --policy/--context to repo content would be repository content deciding
        what runs, the exact thing the template's empty defaults prevent."""
        r = subprocess.run([str(WRAPPER)], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--subject", r.stderr + r.stdout)


if __name__ == "__main__":
    unittest.main()
