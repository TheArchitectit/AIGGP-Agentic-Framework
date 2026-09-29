# // spec: ci-sec-01, mon-sec-02
"""Supply-chain audit tests for shipped templates (audit C-layer):

- every `uses:` in templates/ and the framework's own workflows is pinned to a
  40-hex commit SHA (mutable tags are rejected);
- Containerfile FROM lines are digest-pinned; no `:latest` image references;
- the two quadlets declare the canonical secrets mechanism
  (`EnvironmentFile=`), and no doc instructs a raw env file inside a
  `.container.d/` drop-in (the unparseable form).
"""
import re
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


if __name__ == "__main__":
    unittest.main()
