# spec: fw-corruption-02
"""Read immutable Git ranges with trusted Git and fixed diff settings."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import tempfile

GIT = "/usr/bin/git"
_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


class GitRangeError(ValueError):
    """The checkout does not contain the requested immutable Git range."""


def _environment(objects: Path | None = None) -> dict[str, str]:
    env = {
        "PATH": os.defpath,
        "LC_ALL": "C",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_ALLOW_PROTOCOL": "",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_NO_LAZY_FETCH": "1",
    }
    if objects is not None:
        env["GIT_OBJECT_DIRECTORY"] = str(objects)
    return env


def run_git(root: Path, *args: str, objects: Path | None = None):
    """Run the absolute system Git with no caller or repository config hooks."""
    return subprocess.run(
        [GIT, "--no-replace-objects", "--literal-pathspecs", "-C", str(root), *args],
        capture_output=True, env=_environment(objects), check=False,
    )


def git_bytes(root: Path, *args: str, objects: Path | None = None) -> bytes:
    result = run_git(root, *args, objects=objects)
    if result.returncode:
        raise GitRangeError("Git could not resolve the requested repository data")
    return result.stdout


def git_text(root: Path, *args: str, objects: Path | None = None) -> str:
    return os.fsdecode(git_bytes(root, *args, objects=objects)).removesuffix("\n")


@dataclass(frozen=True)
class CommittedRange:
    root: Path
    git_dir: Path
    objects: Path
    base: str
    head: str

    def run(self, *args: str):
        return run_git(self.git_dir, *args, objects=self.objects)

    def diff(self) -> str:
        result = self.run(
            "-c", "core.quotePath=true", "diff", "--no-ext-diff", "--no-textconv",
            "--no-color", "--unified=0", "--diff-algorithm=myers",
            "--find-renames=50%", "--inter-hunk-context=0",
            "--src-prefix=a/", "--dst-prefix=b/", self.base, self.head, "--",
        )
        if result.returncode:
            raise GitRangeError("could not read the bound committed diff")
        return result.stdout.decode("utf-8", errors="surrogateescape")


@contextmanager
def committed_range_view(root: Path, base: str, head: str):
    """Yield an isolated bare view over the checkout's exact commit objects."""
    root = root.resolve()
    if not _OID.fullmatch(base or "") or not _OID.fullmatch(head or ""):
        raise GitRangeError("a committed range requires full Git object IDs")
    if len(base) != len(head):
        raise GitRangeError("range commit IDs use different object formats")
    top = Path(git_text(root, "rev-parse", "--show-toplevel")).resolve()
    if top != root:
        raise GitRangeError("range root must be the checkout root")
    object_path = git_text(root, "rev-parse", "--path-format=absolute",
                           "--git-path", "objects")
    objects = Path(object_path)
    if not objects.is_absolute() or not objects.is_dir():
        raise GitRangeError("could not locate the checkout object database")
    object_format = "sha256" if len(base) == 64 else "sha1"
    with tempfile.TemporaryDirectory(prefix="aiggp-committed-range-",
                                     dir="/tmp") as scratch:
        initialized = subprocess.run(
            [GIT, "init", "--bare", "--quiet", "--template=",
             f"--object-format={object_format}", scratch],
            capture_output=True, env=_environment(), check=False,
        )
        if initialized.returncode:
            raise GitRangeError("could not create isolated committed-object view")
        view = CommittedRange(root, Path(scratch), objects, base, head)
        for oid in (base, head):
            check = view.run("cat-file", "-t", oid)
            if check.returncode or check.stdout.strip() != b"commit":
                raise GitRangeError("range does not resolve to immutable commits")
        yield view
