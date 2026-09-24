#!/usr/bin/env python3
"""The shipped secret-scanning template must enforce the contract this repo runs.

The template previously told consumers to run `gitleaks/gitleaks-action@v2` on a
hosted runner — a marketplace action, a licence question for organisations, and
a different mechanism from anything this repository exercised — while two of its
three other jobs printed the matched line (republishing the secret) and never
failed the build. It looked like protection and was not.

Two kinds of assertion live here, and the difference matters:

  * Static ones over the PARSED yaml — which actions run, and whether the
    template's scanner version and checksum match this repository's own CI. A
    comment that names a removed action is documentation, not a dependency, so
    these read the parsed document rather than the file text.

  * Behavioural ones that execute the step bodies with stubbed tools. Text
    assertions are how this suite first went wrong: a mutation that turns a
    guard into `if false;` leaves every string it asserted on exactly where it
    was, and the suite stayed green while the guard was dead. Four such
    mutations survived the first draft of this file. So the checks that protect
    a consumer — the fetch that must not happen when a scanner is present, the
    checksum that must reject wrong bytes, the gate that must be present, the
    scope line that must appear, the .env job that must fail — are run, not
    read.
"""
from __future__ import annotations

import contextlib
import os
import re
import shutil
import stat
import subprocess
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "templates" / "github-workflows" / "secret-validation.yml"
CI = REPO / ".github" / "workflows" / "ci.yml"
GATE = REPO / "scripts" / "secret-scan.sh"
BASH = "/bin/bash"

# Recording stubs for the scanner step. `install` is stubbed as well as `curl`
# for two reasons: a success path must never write into the real
# /usr/local/bin from a test, and "the checksum ran before the bytes were used"
# is only observable if installation is observable.
CURL_STUB = """#!/bin/bash
: > "{sb}/curl-called"
out=""
while [ $# -gt 0 ]; do
  case "$1" in -o) out="$2"; shift 2 ;; *) shift ;; esac
done
[ -n "$out" ] || exit 0
echo "not the tarball" > "$out"
"""

INSTALL_STUB = """#!/bin/bash
: > "{sb}/install-called"
exit 0
"""


def _all_uses(doc: dict) -> list[str]:
    """Every `uses:` the workflow would actually execute, from the parsed YAML."""
    found = []
    for job in (doc.get("jobs") or {}).values():
        for step in (job.get("steps") or []):
            if isinstance(step, dict) and "uses" in step:
                found.append(str(step["uses"]))
    return found


def _job_steps(doc: dict, job: str) -> list[dict]:
    return [s for s in doc["jobs"][job]["steps"] if isinstance(s, dict)]


def _run_text(doc: dict, job: str) -> str:
    return "\n".join(str(s.get("run", "")) for s in _job_steps(doc, job))


def _step_run(doc: dict, job: str, name_contains: str) -> str:
    for s in _job_steps(doc, job):
        if name_contains in str(s.get("name", "")):
            return str(s.get("run", ""))
    raise AssertionError(f"no step in job {job!r} whose name contains "
                         f"{name_contains!r}")


def _write_exec(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _pin(text: str) -> tuple[str | None, str | None]:
    version = re.search(r"VERSION=([0-9][0-9.]*)", text)
    checksum = re.search(r"SHA256=([0-9a-f]{64})", text)
    return (version.group(1) if version else None,
            checksum.group(1) if checksum else None)


class TestSecretValidationTemplate(unittest.TestCase):
    def setUp(self):
        self.text = TEMPLATE.read_text(encoding="utf-8")
        self.doc = yaml.safe_load(self.text)

    # --- it calls the gate, rather than reimplementing it --------------------

    def test_template_invokes_the_gate_script(self):
        """Asserted on the step that runs, not on the file: the SETUP header
        also says `scripts/secret-scan.sh`, so a text search is satisfied by the
        prose even after the invocation itself has been broken."""
        run = _step_run(self.doc, "secret-scan", "Secret scan (")
        self.assertIn("bash scripts/secret-scan.sh", run)
        self.assertTrue(GATE.is_file(), "the gate it invokes is missing")

    def test_template_fails_closed_when_the_gate_is_absent(self):
        """Executed: with no gate script, the step must fail rather than pass a
        job that scanned nothing."""
        with self._scratch() as tmp:
            run = _step_run(self.doc, "secret-scan", "Gate present")
            r = self._bash(run, tmp)
            self.assertNotEqual(r.returncode, 0,
                                "a missing gate produced a passing step")
            self.assertIn("scripts/secret-scan.sh is missing", r.stdout + r.stderr)
            _write_exec(tmp / "scripts" / "secret-scan.sh", "#!/bin/bash\nexit 0\n")
            r2 = self._bash(run, tmp)
            self.assertEqual(r2.returncode, 0,
                             f"the check fails even when the gate is present: "
                             f"{r2.stdout}{r2.stderr}")

    def test_the_scan_step_fails_when_the_gate_does_not_report_a_scope(self):
        """Non-vacuity, executed. A gate that exits 0 without naming a scope did
        not run; the step must not read that as a clean repository."""
        run = _step_run(self.doc, "secret-scan", "Secret scan (")
        with self._scratch() as tmp:
            _write_exec(tmp / "scripts" / "secret-scan.sh",
                        '#!/bin/bash\necho "did nothing"\nexit 0\n')
            r = self._bash(run, tmp)
            self.assertNotEqual(r.returncode, 0,
                                "a gate that never ran was accepted as a pass")
            self.assertIn("did not run", r.stdout + r.stderr)

    def test_the_scan_step_reports_its_scope_and_propagates_a_finding(self):
        run = _step_run(self.doc, "secret-scan", "Secret scan (")
        with self._scratch() as tmp:
            gate = tmp / "scripts" / "secret-scan.sh"
            _write_exec(gate, '#!/bin/bash\necho "[secret-scan] scope: working tree"\nexit 0\n')
            ok = self._bash(run, tmp)
            self.assertEqual(ok.returncode, 0,
                             f"a clean scoped run failed: {ok.stdout}{ok.stderr}")
            _write_exec(gate, '#!/bin/bash\necho "[secret-scan] scope: working tree"\n'
                              'echo "[secret-scan] FINDING: r p:1 (abc)"\nexit 1\n')
            bad = self._bash(run, tmp)
            self.assertEqual(bad.returncode, 1,
                             "the gate's failure was swallowed by the step")

    # --- the mechanism is the pinned binary, not a marketplace action --------

    def test_no_marketplace_scanning_action(self):
        for ref in _all_uses(self.doc):
            self.assertNotIn("gitleaks-action", ref,
                             f"the template still runs {ref}")

    def test_no_floating_action_reference(self):
        """An action referenced by tag is an action referenced by whatever the
        tag points at today."""
        floating = [r for r in _all_uses(self.doc) if re.search(r"@v\d+$", r)]
        self.assertEqual(floating, [],
                         f"floating action reference(s): {floating}")

    def test_every_action_is_pinned_by_commit_sha(self):
        uses = _all_uses(self.doc)
        self.assertTrue(uses, "the template declares no actions")
        for ref in uses:
            _, _, sha = ref.partition("@")
            self.assertRegex(sha, r"^[0-9a-f]{40}$",
                             f"action not pinned by SHA: {ref}")

    def test_a_present_scanner_is_used_without_fetching_anything(self):
        """Executed in a sandbox holding only a scanner: this is the self-hosted
        path, and the promise is that it does not download. Asserting the
        `command -v` string survives is not that promise — `if false;` keeps the
        string. The sandbox exists because the first draft of this test passed
        or failed according to whether the HOST had gitleaks installed, which is
        a measurement of the machine rather than of the template."""
        run = _step_run(self.doc, "secret-scan", "Provide the pinned scanner")
        with self._scratch() as tmp:
            sb = self._sandbox(tmp, scanner=True)
            r = self._bash(run, tmp, sandbox=sb)
            self.assertEqual(r.returncode, 0, f"{r.stdout}{r.stderr}")
            self.assertFalse((sb / "curl-called").exists(),
                             "a runner that already has the pinned scanner "
                             "downloaded it anyway")

    def test_fetched_scanner_bytes_are_verified_against_the_pin(self):
        """Executed: wrong bytes must be rejected before anything is extracted or
        installed. Measured against the real release — the vendor's checksum file
        and the artifact agree on 8.30.1 — so what is left to pin is that the
        check runs before the bytes are used."""
        run = _step_run(self.doc, "secret-scan", "Provide the pinned scanner")
        self.assertIn("sha256sum -c", run)
        with self._scratch() as tmp:
            sb = self._sandbox(tmp, scanner=False)
            r = self._bash(run, tmp, sandbox=sb)
            self.assertNotEqual(r.returncode, 0,
                                "wrong bytes were accepted as the pinned release")
            self.assertTrue((sb / "curl-called").exists(),
                            "the fetch did not happen, so this proves nothing "
                            "about verification")
            self.assertFalse((sb / "install-called").exists(),
                             "unverified bytes reached the install step")

    def test_scanner_version_is_asserted_after_install(self):
        run = _step_run(self.doc, "secret-scan", "pinned version")
        self.assertIn("gitleaks version", run)

    # --- the one assertion no future author is trusted to remember -----------

    def test_template_and_ci_name_the_same_scanner_pin(self):
        t_ver, t_sum = _pin(self.text)
        c_ver, c_sum = _pin(CI.read_text(encoding="utf-8"))
        self.assertIsNotNone(t_ver, "the template declares no scanner VERSION")
        self.assertIsNotNone(c_ver, "ci.yml declares no scanner VERSION")
        self.assertEqual(t_ver, c_ver,
                         f"scanner version drift: template {t_ver}, ci {c_ver}")
        self.assertEqual(t_sum, c_sum,
                         f"scanner checksum drift: template {t_sum}, ci {c_sum}")

    # --- the jobs that republished secrets are gone --------------------------

    def test_the_job_that_echoed_matched_lines_is_gone(self):
        """The old hardcoded-secrets job grepped credential-shaped assignments,
        printed the matching line, and never failed the build."""
        self.assertNotIn('echo "$MATCHES"', self.text)
        self.assertNotIn(r"password\s*=", self.text)
        self.assertNotIn("ISSUES_FOUND", self.text)

    def test_the_warn_only_credential_file_job_is_gone(self):
        self.assertNotIn("credential files", self.text.lower())
        self.assertNotIn("*.pem", self.text)

    def test_the_env_check_still_fails_on_a_committed_env_file(self):
        """Executed: kept because it covers what a ruleset cannot — a committed
        .env whose contents are not key-shaped. It prints filenames, never
        contents, and it must still fail."""
        run = _step_run(self.doc, "check-env-files", "No committed .env")
        with self._scratch() as tmp:
            self.assertEqual(self._bash(run, tmp).returncode, 0,
                             "the .env check fails on an empty tree")
            (tmp / ".env").write_text("PLACEHOLDER=1\n")
            r = self._bash(run, tmp)
            self.assertNotEqual(r.returncode, 0,
                                "a committed .env no longer fails the build")
            self.assertIn(".env", r.stdout + r.stderr)
            self.assertNotIn("PLACEHOLDER=1", r.stdout + r.stderr,
                             "the .env check printed the file's contents")

    # --- shape ---------------------------------------------------------------

    def test_yaml_parses_and_both_jobs_are_declared(self):
        jobs = self.doc.get("jobs") or {}
        self.assertIn("secret-scan", jobs)
        self.assertIn("check-env-files", jobs)

    # --- harness -------------------------------------------------------------

    @contextlib.contextmanager
    def _scratch(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def _sandbox(self, tmp, scanner: bool):
        """A PATH holding only what the scanner step needs.

        The step picks its branch with `command -v gitleaks`, so running it
        against the ambient PATH measures the machine rather than the template:
        on a host that happens to have gitleaks installed, the fetch path is
        unreachable and the checksum assertion passes without ever being
        exercised. Only `sha256sum` and `tar` are the real tools here; `curl`
        and `install` record that they were called.
        """
        sb = tmp / "sandbox"
        sb.mkdir(exist_ok=True)
        for tool in ("sha256sum", "tar"):
            src = shutil.which(tool)
            if src is None:
                self.skipTest(f"{tool} is not on this host")
            os.symlink(src, sb / tool)
        _write_exec(sb / "curl", CURL_STUB.format(sb=sb))
        _write_exec(sb / "install", INSTALL_STUB.format(sb=sb))

        if scanner:
            _write_exec(sb / "gitleaks", '#!/bin/bash\necho "8.30.1"\n')
        return sb

    def _bash(self, run: str, tmp, sandbox=None):
        env = {
            **os.environ,
            "GITHUB_WORKSPACE": str(tmp),
            "RUNNER_TEMP": str(tmp),
            "EV_BEFORE": "a" * 40,
            "EV_AFTER": "b" * 40,
        }
        env.pop("PR_BASE", None)
        env.pop("PR_HEAD", None)
        env["PATH"] = str(sandbox) if sandbox is not None else os.environ["PATH"]
        return subprocess.run([BASH, "-c", run], cwd=str(tmp), env=env,
                              capture_output=True, text=True, timeout=60)


if __name__ == "__main__":
    unittest.main()
