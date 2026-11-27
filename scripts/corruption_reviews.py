"""Exact, separately authorized substitution findings for the committed-range gate."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile

CATALOG = Path("/etc/aiggp/corruption-reviews.json")
RUN_BINDINGS = Path("/run/aiggp/corruption-reviews")
ASSERTION = "fw-corruption-01"
TREATMENT = "EXCEPTION-ADVISORY"
BINDING_TYPE = "aiggp.corruption-review-binding/v1"
CATALOG_TYPE = "aiggp.corruption-review-catalog/v1"
OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
SUBJECT = re.compile(r"github:[a-z0-9.-]+:[1-9][0-9]*")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}")
FINDING = re.compile(r"substitution-flip:([0-9a-f]+):([0-9a-f]+):([1-9][0-9]*)")
LIMIT = 1024 * 1024


class ReviewError(ValueError):
    """The external policy, bound input or requested review mode is invalid."""


def _protected(fd, directory=False):
    info = os.fstat(fd)
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if not kind(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ReviewError("control-plane input requires root ownership and protected permissions")


def read_protected(path):
    """Read a bounded regular file through protected, symlink-free directories."""
    if not path.is_absolute() or ".." in path.parts:
        raise ReviewError("invalid control-plane path")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    directory = os.open("/", flags | os.O_DIRECTORY)
    try:
        _protected(directory, directory=True)
        for component in path.parts[1:-1]:
            child = os.open(component, flags | os.O_DIRECTORY, dir_fd=directory)
            os.close(directory)
            directory = child
            _protected(directory, directory=True)
        fd = os.open(path.name, flags | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, "rb") as stream:
            _protected(stream.fileno())
            data = stream.read(LIMIT + 1)
    finally:
        os.close(directory)
    if len(data) > LIMIT:
        raise ReviewError("control-plane input exceeds size limit")
    return data


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReviewError("duplicate control-plane field")
        result[key] = value
    return result


def _object(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields.split()):
        raise ReviewError("unexpected or missing control-plane fields")
    return value


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and value.isprintable()


def _time(value):
    if not _text(value) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value
    ):
        raise ReviewError("expected UTC timestamp")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ReviewError("invalid UTC timestamp") from error


def _oid(value):
    return isinstance(value, str) and OID.fullmatch(value) and set(value) != {"0"}


def _subject(value):
    return isinstance(value, str) and SUBJECT.fullmatch(value)


def _path(value):
    if not _text(value):
        return False
    if '"' in value or "\\" in value:
        return False  # Git quotes these names in unified-diff headers.
    p = PurePosixPath(value)
    return bool(p.parts) and not p.is_absolute() and ".." not in p.parts and str(p) == value


@dataclass(frozen=True)
class Grant:
    identity: str
    start: datetime
    end: datetime


def _grant(entry):
    _object(
        entry,
        "exception_id subject_ref assertion_id subject_path finding_fingerprint owner "
        "reason approving_authority created_at expires_at enforcement_treatment remediation_ref",
    )
    fp = _object(
        entry["finding_fingerprint"],
        "assertion_id assertion_version subject_location violation_key",
    )
    if (
        not _text(entry["exception_id"])
        or not SAFE_ID.fullmatch(entry["exception_id"])
        or not _subject(entry["subject_ref"])
        or not _path(entry["subject_path"])
        or entry["assertion_id"] != ASSERTION
        or fp["assertion_id"] != ASSERTION
        or type(fp["assertion_version"]) is not int
        or fp["assertion_version"] != 1
        or fp["subject_location"] != entry["subject_path"]
        or entry["enforcement_treatment"] != TREATMENT
        or not all(
            _text(entry[f]) for f in ("owner", "reason", "approving_authority", "remediation_ref")
        )
        or not _text(fp["violation_key"])
    ):
        raise ReviewError("invalid reviewed substitution record")
    match = FINDING.fullmatch(fp["violation_key"])
    if match is None:
        raise ReviewError("invalid substitution fingerprint")
    before, after, line = match.groups()
    if not _oid(before) or not _oid(after) or len(before) != len(after) or before == after:
        raise ReviewError("invalid ordered blob pair")
    start, end = _time(entry["created_at"]), _time(entry["expires_at"])
    if start >= end:
        raise ReviewError("invalid exception validity interval")
    key = (entry["subject_ref"], entry["subject_path"], before, after, int(line))
    return key, Grant(entry["exception_id"], start, end)


def _catalog(data):
    document = _object(json.loads(data, object_pairs_hook=_unique), "api_version exceptions")
    if document["api_version"] != CATALOG_TYPE or not isinstance(document["exceptions"], list):
        raise ReviewError("invalid exception catalog")
    grants, ids = {}, set()
    for entry in document["exceptions"]:
        key, grant = _grant(entry)
        if key in grants or grant.identity in ids:
            raise ReviewError("duplicate reviewed transition or exception identity")
        grants[key] = grant
        ids.add(grant.identity)
    return grants


def _git(root, *args, objects=None):
    """The protected Linux evaluator selects Git and its environment."""
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
    return subprocess.run(
        ["/usr/bin/git", "--no-replace-objects", "--literal-pathspecs", "-C", str(root), *args],
        env=env,
        capture_output=True,
        check=False,
    )


def _blob(git_dir, objects, commit, path):
    proc = _git(git_dir, "ls-tree", "-z", "--full-tree", commit, "--", path, objects=objects)
    if proc.returncode:
        raise ReviewError("could not resolve reviewed Git tree")
    rows = proc.stdout.split(b"\0")
    if len(rows) != 2 or rows[-1]:
        return None
    meta, sep, name = rows[0].partition(b"\t")
    fields = meta.split()
    if (
        not sep
        or name != os.fsencode(path)
        or len(fields) != 3
        or fields[1] != b"blob"
        or fields[0] not in {b"100644", b"100755"}
    ):
        return None
    return fields[2].decode("ascii")


@contextmanager
def open_reviews(root, base, head):
    # Configuration, refs, worktree attributes and external diff drivers from the
    # subject must not decide how the independently authorized range is paired.
    with tempfile.TemporaryDirectory(prefix="aiggp-commits-", dir="/tmp") as scratch:
        yield Reviews(root, base, head, Path(scratch))


class Reviews:
    def __init__(self, root, base, head, git_dir):
        self.root, self.base, self.head = root.resolve(), base, head
        if self.root in CATALOG.parents or self.root in RUN_BINDINGS.parents:
            raise ReviewError("authority must be outside the subject checkout")
        if not _oid(base) or not _oid(head) or len(base) != len(head):
            raise ReviewError("reviewed mode requires two full commit object IDs")
        self.git_dir = git_dir
        top = _git(self.root, "rev-parse", "--show-toplevel")
        if top.returncode or top.stdout.removesuffix(b"\n") != os.fsencode(str(self.root)):
            raise ReviewError("reviewed mode requires the checkout root")
        objects = _git(self.root, "rev-parse", "--path-format=absolute", "--git-path", "objects")
        self.objects = Path(os.fsdecode(objects.stdout.removesuffix(b"\n")))
        if objects.returncode or not self.objects.is_absolute() or not self.objects.is_dir():
            raise ReviewError("could not locate the checkout object database")
        fmt = "sha1" if len(base) == 40 else "sha256"
        if _git(
            git_dir, "init", "--bare", "--quiet", "--template=", "--object-format=" + fmt
        ).returncode:
            raise ReviewError("could not create isolated committed-object view")
        for oid in (base, head):
            kind = _git(git_dir, "cat-file", "-t", oid, objects=self.objects)
            if kind.returncode or kind.stdout.strip() != b"commit":
                raise ReviewError("reviewed range does not resolve to bound commits")
        name = hashlib.sha256(os.fsencode(str(self.root))).hexdigest() + ".json"
        self.binding_path = RUN_BINDINGS / name
        self.binding_bytes = read_protected(self.binding_path)
        binding = _object(
            json.loads(self.binding_bytes, object_pairs_hook=_unique),
            "api_version checkout subject_ref base head issued_at expires_at catalog_sha256",
        )
        self.subject = binding["subject_ref"]
        self.start, self.end = _time(binding["issued_at"]), _time(binding["expires_at"])
        self.digest = binding["catalog_sha256"]
        if (
            binding["api_version"] != BINDING_TYPE
            or self.start >= self.end
            or binding["checkout"] != str(self.root)
            or (binding["base"], binding["head"]) != (base, head)
            or not _subject(self.subject)
            or not _text(self.digest)
            or not re.fullmatch("[0-9a-f]{64}", self.digest)
        ):
            raise ReviewError("run binding does not authorize this checkout and range")
        data = read_protected(CATALOG)
        if hashlib.sha256(data).hexdigest() != self.digest:
            raise ReviewError("current catalog differs from the bound catalog")
        self.grants = _catalog(data)
        self.blobs = {}
        self.used = {}
        self.check_current()

    def diff(self):
        result = _git(
            self.git_dir,
            "-c",
            "core.quotePath=true",
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--no-color",
            "--unified=0",
            "--diff-algorithm=myers",
            "--find-renames=50%",
            "--inter-hunk-context=0",
            "--src-prefix=a/",
            "--dst-prefix=b/",
            self.base,
            self.head,
            "--",
            objects=self.objects,
        )
        if result.returncode:
            raise ReviewError("could not read the bound committed diff")
        return result.stdout.decode("utf-8", errors="surrogateescape")

    def check_current(self):
        now = datetime.now(timezone.utc)
        if (
            not self.start <= now < self.end
            or any(not grant.start <= now < grant.end for grant in self.used.values())
            or read_protected(self.binding_path) != self.binding_bytes
            or hashlib.sha256(read_protected(CATALOG)).hexdigest() != self.digest
        ):
            raise ReviewError("binding or reviewed transition expired or was withdrawn")

    def match(self, path, line):
        if not _path(path):
            return None
        if path not in self.blobs:
            self.blobs[path] = (
                _blob(self.git_dir, self.objects, self.base, path),
                _blob(self.git_dir, self.objects, self.head, path),
            )
        before, after = self.blobs[path]
        grant = self.grants.get((self.subject, path, before, after, line))
        now = datetime.now(timezone.utc)
        if grant is not None and grant.start <= now < grant.end:
            self.used[grant.identity] = grant
            return grant.identity
        return None
