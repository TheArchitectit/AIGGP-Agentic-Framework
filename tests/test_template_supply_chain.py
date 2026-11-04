# // spec: ci-sec-01, mon-sec-02, fleet-add-01, ci-run-01, ci-match-01, ci-self-01, doc-version-01, doc-overlay-01, fw-ci-01, fw-ci-02, fw-ci-03, rule-behavior-01
"""Supply-chain audit tests for shipped templates (audit C-layer):

- every `uses:` in templates/ and the framework's own workflows is pinned to a
  40-hex commit SHA (mutable tags are rejected);
- Containerfile FROM lines are digest-pinned; no `:latest` image references;
- the two quadlets declare the canonical secrets mechanism
  (`EnvironmentFile=`), and no doc instructs a raw env file inside a
  `.container.d/` drop-in (the unparseable form).
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = REPO / "templates"
WORKFLOWS = REPO / ".github" / "workflows"

USES_RE = re.compile(r"uses:\s*(\S+)")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class TestActionPinning(unittest.TestCase):
    def _uses_lines(self):
        files = list(TEMPLATES.rglob("*.yml")) + list(WORKFLOWS.glob("*.yml")) \
            + list(WORKFLOWS.glob("*.yaml"))
        for f in files:
            for i, line in enumerate(f.read_text().splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                m = USES_RE.search(line)
                if m:
                    yield f, i, m.group(1)

    def test_every_uses_is_sha_pinned(self):
        offenders = []
        for f, i, ref in self._uses_lines():
            if "@" not in ref:
                offenders.append(f"{f.relative_to(REPO)}:{i} {ref} (no ref)")
                continue
            _, _, rev = ref.rpartition("@")
            if not SHA_RE.match(rev):
                offenders.append(f"{f.relative_to(REPO)}:{i} {ref} (mutable ref)")
        self.assertEqual(offenders, [],
                         "actions must be pinned by 40-hex SHA:\n" +
                         "\n".join(offenders))


class TestImagePinning(unittest.TestCase):
    def test_no_latest_tags_in_templates(self):
        offenders = []
        for f in list(TEMPLATES.rglob("*.container")) + \
                list(TEMPLATES.rglob("Containerfile")) + \
                list(TEMPLATES.rglob("*.yml")):
            for i, line in enumerate(f.read_text().splitlines(), 1):
                s = line.strip()
                if s.startswith("#"):
                    continue
                if s.startswith("Image=") or s.startswith("FROM "):
                    if ":latest" in s:
                        offenders.append(f"{f.relative_to(REPO)}:{i} {s}")
        self.assertEqual(offenders, [], "no :latest image refs:\n" +
                         "\n".join(offenders))

    def test_containerfile_froms_are_digest_pinned(self):
        offenders = []
        for f in TEMPLATES.rglob("Containerfile"):
            for i, line in enumerate(f.read_text().splitlines(), 1):
                if line.strip().startswith("FROM "):
                    if "@sha256:" not in line:
                        offenders.append(f"{f.relative_to(REPO)}:{i} {line.strip()}")
        self.assertEqual(offenders, [], "FROMs must be digest-pinned:\n" +
                         "\n".join(offenders))


class TestCanonicalSecretsMechanism(unittest.TestCase):
    def test_quadlets_declare_environment_file(self):
        for name in ("runner/self-hosted-runner.container",
                     "runner-monitor/devgate-hub.container"):
            text = (TEMPLATES / name).read_text()
            self.assertIn("EnvironmentFile=", text,
                          f"{name} must declare the secrets env file")

    def test_docs_do_not_instruct_raw_env_in_container_d(self):
        """The old instructions wrote a bare `RUNNER_TOKEN=` file into
        `.container.d/` — a quadlet drop-in is INI, so the file never parsed.
        The canonical form is the quadlet's EnvironmentFile=."""
        offenders = []
        for f in Path(REPO / "docs").rglob("*.md"):
            text = f.read_text()
            for i, line in enumerate(text.splitlines(), 1):
                if ".container.d" in line and "drop-in" in line:
                    if "not a" in line or "NOT a" in line or "expects" in line:
                        continue  # explanatory mention, not an instruction
                    offenders.append(f"{f.relative_to(REPO)}:{i} {line.strip()}")
        self.assertEqual(offenders, [],
                         "docs must not instruct raw env files in drop-ins:\n" +
                         "\n".join(offenders))


class TestFleetAddRunnerWalkthrough(unittest.TestCase):
    """fleet-add-01: documented N+1th runner procedure."""

    def test_add_a_runner_walkthrough_and_discoverability(self):
        walkthrough = TEMPLATES / "runner" / "add-a-runner.md"
        readme = TEMPLATES / "runner" / "README.md"
        self.assertTrue(walkthrough.is_file(), "templates/runner/add-a-runner.md missing")
        self.assertIn("add-a-runner.md", readme.read_text(encoding="utf-8"),
                      "templates/runner/README.md must link to add-a-runner.md")
        text = walkthrough.read_text(encoding="utf-8")
        self.assertIn("https://", text)
        self.assertIn("SSH", text)
        self.assertIn("EnvironmentFile", text)
        self.assertIsNone(
            re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text),
            "add-a-runner.md must not contain literal IPv4 addresses")


class TestCiTemplateAndFrameworkContracts(unittest.TestCase):
    """ci-run-01, ci-match-01, ci-self-01, fw-ci-01, fw-ci-02, fw-ci-03."""

    def test_drift_scan_and_gates_templates_run_named_gates(self):
        drift = (TEMPLATES / "github-workflows" / "drift-scan.yml").read_text(encoding="utf-8")
        self.assertIn("fetch-depth: 0", drift)
        self.assertIn("typescript@5", drift)
        self.assertIn("NOT_RUN", drift)
        compliance = (TEMPLATES / "github-workflows" / "guardrails-compliance.yml").read_text(encoding="utf-8")
        self.assertIn("environment.yml", compliance)
        self.assertIn(".env.example", compliance)

    def test_framework_ci_runs_suite_and_gates(self):
        ci = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        for needle in ("pytest", "run-tests.mjs", "guardrails-scan.mjs",
                       "semantic-scan.mjs", "failure_registry_check.py",
                       "regression_check.py", "--fail-if-empty"):
            self.assertIn(needle, ci, f"ci.yml missing {needle}")


class TestDocTruthAndBehaviorRuleContracts(unittest.TestCase):
    """doc-version-01, doc-overlay-01, rule-behavior-01."""

    def test_version_and_changelog_agreement(self):
        ver = (REPO / "VERSION").read_text(encoding="utf-8").strip()
        changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertTrue(ver, "VERSION must be non-empty")
        self.assertIn(f"## [{ver}]", changelog,
                      "VERSION must have its own CHANGELOG release section")
        self.assertNotIn("intentionally disagree", changelog,
                         "doc-version-01 forbids version artifacts that "
                         "deliberately disagree")
        gate = REPO / "scripts" / "check_version_truth.py"
        proc = subprocess.run(
            [sys.executable, str(gate), "--repo", str(REPO)],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0,
                         f"version-truth gate must pass on this tree: "
                         f"{proc.stderr}")

    def test_overlay_and_behavior_rules_contracts(self):
        agents = (REPO / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(".guardrails/", agents)
        extracted = REPO / ".guardrails" / "prevention-rules" / "extracted-rules.json"
        self.assertFalse(extracted.exists(),
                         "extracted-rules.json must not ship in prevention-rules")
        skill_dir = TEMPLATES / "skills"
        self.assertTrue(skill_dir.is_dir(), "templates/skills must exist")


if __name__ == "__main__":
    unittest.main()
