# // spec: img-cycle-04, coh-id-04
"""The re-pin harness: a throwaway git repository the operation runs against.

`scripts/re-pin-evaluator-identity.sh` is an OPERATOR tool — it commits — so
testing it means giving it a repository to commit in. This builds one: a real
temporary git repo carrying only the two files the operation edits, plus a
`bin/` of stubs (`curl` answering the registry's token and manifest endpoints,
`podman` answering a digest NO registry serves) prepended to PATH.

It lives here rather than in the suite for two reasons. It is a fixture, and
this is where ten other suites keep theirs (`tests/fixtures/coherence/`). And
the suite that used to hold it inline crossed the repository's 600-line hard
limit for test files when the exit-6 test was added — the honest response to
that gate being to stop growing the file rather than to move the limit.

The stubs are deliberately hostile rather than convenient: the podman stub
reports a local-storage digest no registry serves, so a run that resolved the
identity through podman instead of the registry API would record that value
and be visible.

Deterministic and hermetic: no network, no host clock, and an identity
supplied through the environment (see `identity()`), so nothing here depends
on whichever git config the machine happens to have.
"""
import json
import os
import re
import subprocess
from pathlib import Path

# The DevGate checkout this harness ships in. Named by parent-count, which is
# exactly what broke when this file moved out of tests/ into tests/fixtures/:
# the anchor silently became tests/, SCRIPT became
# tests/scripts/re-pin-evaluator-identity.sh, and every test failed with
# `bash: …: No such file or directory`. A parent-count is stable only while the
# file stays where it is, so it is now checked rather than trusted — this
# repository already carries the contract for why (scripts/lib/project_root.py,
# root-anchor-01): a root that silently resolves somewhere else is worse than
# one that refuses, because the failure surfaces far away from the cause.
REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "re-pin-evaluator-identity.sh"
if not SCRIPT.is_file():
    raise RuntimeError(
        f"the re-pin harness resolved the DevGate checkout as {REPO}, where "
        f"{SCRIPT.relative_to(REPO)} does not exist — this file has moved, and "
        "the anchor above needs one more (or one fewer) parent")

IMAGE = "ghcr.io/thearchitectit/aiggp-agentic-framework/devgate-coherence"
SERVED = "sha256:" + "a" * 64
LOCAL = "sha256:" + "f" * 64

TEMPLATE_BODY = """\
name: spec coherence
env:
      DEVGATE_REPO: https://github.com/TheArchitectit/AIGGP-Agentic-Framework.git
      DEVGATE_PIN: {pin}
      COHERENCE_IMAGE: {image}
      COHERENCE_PROFILE: {profile}
      COHERENCE_IMAGE_MANIFEST_DIGEST: {digest}
"""

CURL_STUB = """\
#!/usr/bin/env bash
args="$*"
case "$args" in
  *"/token"*)
    echo '{"token":"stub-token"}'
    exit 0 ;;
esac
if [[ "$args" == *"/manifests/"* ]]; then
  printf 'HTTP/2 200\\r\\ndocker-content-digest: __SERVED__\\r\\n\\r\\n'
  exit 0
fi
exit 1
"""

# Deliberately hostile: `image inspect` answers with a digest no registry
# serves. If the operation ever resolves the identity through podman instead of
# the registry API, the recorded value becomes this — and the test sees it.
PODMAN_STUB = """\
#!/usr/bin/env bash
case "$1" in
  pull) exit "${STUB_PULL_RC:-0}" ;;
  *) echo "__LOCAL__" ;;
esac
"""


def identity() -> dict:
    """The committer identity, supplied through the ENVIRONMENT.

    Two reasons this is not optional, and the second is why it must be the
    environment rather than config:

    * Hermeticity. These tests commit — the fixtures do, and the operation
      under test does. A suite that passes only because the operator's
      ~/.gitconfig happens to carry a user.name is not testing the operation;
      on a runner with no such config every one of those commits fails. That
      is not hypothetical: run 36061428590 failed 3 tests with
      `fatal: empty ident name (for <runner@…>) not allowed` and the
      operation's exit 6, while the same suite was green locally.
    * The fixtures read no config at all (`GIT_CONFIG_GLOBAL=/dev/null`), so
      `user.name` in a config file would not be read even if it existed. Git
      consults GIT_AUTHOR_*/GIT_COMMITTER_* before any config, which is the
      one channel that reaches every git process here, ours and the script's.
    """
    return {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(repo: Path, *args, **env):
    full = dict(os.environ, **identity())
    full.update(env)
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, env=full)


def record(digest: str, image: str = IMAGE, profile: str = "linux-amd64-v1",
            built: str = "2026-01-01") -> str:
    return json.dumps({
        "schema": "execution-profiles",
        "image": image,
        "profiles": [{
            "label": profile,
            "platform": "linux/amd64",
            "image_manifest_digest": digest,
            "base_image": "docker.io/library/python@sha256:" + "b" * 64,
            "semantic_equivalence_group": "default",
            "built": built,
        }],
    }, indent=2) + "\n"


def fixture(tmp: Path, *, digest: str = "sha256:" + "c" * 64,
             image: str = IMAGE, pin: str = None, profile: str = "linux-amd64-v1",
             built: str = "2026-01-01") -> tuple:
    """A minimal git repository carrying the two files the operation edits.

    `pin` is written verbatim when given; otherwise the template's pin is set
    to the initial commit, which is what a correct tree looks like.
    """
    repo = tmp / "repo"
    (repo / "container").mkdir(parents=True)
    (repo / "templates" / "github-workflows").mkdir(parents=True)
    (repo / "container" / "execution-profiles.json").write_text(
        record(digest, image, profile, built))
    (repo / "templates" / "github-workflows" / "spec-coherence.yml").write_text(
        TEMPLATE_BODY.format(pin=pin or "0" * 40, image=image,
                             profile=profile, digest=digest))
    if git(repo, "init", "-q", "-b", "main").returncode != 0:
        raise AssertionError("git init failed in fixture")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "fixture")
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    if pin is None:
        text = (repo / "templates" / "github-workflows" / "spec-coherence.yml").read_text()
        text = re.sub(r"DEVGATE_PIN: \S+", f"DEVGATE_PIN: {head}", text)
        (repo / "templates" / "github-workflows" / "spec-coherence.yml").write_text(text)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "pin to first commit")
        head = git(repo, "rev-parse", "HEAD").stdout.strip()
    return repo, head


def stub_bin(tmp: Path, *, served: str = SERVED, pull_rc: int = 0) -> Path:
    b = tmp / "bin"
    b.mkdir()
    (b / "curl").write_text(CURL_STUB.replace("__SERVED__", served))
    (b / "podman").write_text(PODMAN_STUB.replace("__LOCAL__", LOCAL))
    for p in (b / "curl", b / "podman"):
        p.chmod(0o755)
    return b


def env(repo: Path, binp: Path, **extra) -> dict:
    e = dict(os.environ, **identity())
    e["PATH"] = f"{binp}:{e['PATH']}"
    e["REPIN_REPO_DIR"] = str(repo)
    e["REPIN_IMAGE"] = IMAGE
    e["REPIN_BUILT"] = "2026-09-24"
    e.update(extra)
    return e


def run(repo: Path, binp: Path, **extra):
    return subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True,
                          cwd=str(REPO), env=env(repo, binp, **extra))


def tmpl(repo: Path) -> dict:
    text = (repo / "templates" / "github-workflows" / "spec-coherence.yml").read_text()
    return {m.group(1): m.group(2)
            for m in re.finditer(r"^\s*([A-Z][A-Z0-9_]*):\s*(\S*)\s*$", text, re.M)}


def rec(repo: Path) -> dict:
    return json.loads((repo / "container" / "execution-profiles.json").read_text())
