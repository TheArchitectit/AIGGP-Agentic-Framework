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

from corruption_git import CommittedRange, GitRangeError, committed_range_view

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


# spec: scan-corruption-reviewed-authority-01
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


def _blob(view: CommittedRange, commit: str, path: str):
    proc = view.run("ls-tree", "-z", "--full-tree", commit, "--", path)
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
    # Both review modes read the same exact commits through the shared fixed Git view.
    root = Path(root).resolve()
    if root in CATALOG.parents or root in RUN_BINDINGS.parents:
        raise ReviewError("authority must be outside the subject checkout")
    if not _oid(base) or not _oid(head) or len(base) != len(head):
        raise ReviewError("reviewed mode requires two full commit object IDs")
    try:
        with committed_range_view(root, base, head) as view:
            yield Reviews(root, base, head, view)
    except GitRangeError as exc:
        raise ReviewError(str(exc)) from exc


def run_protected_range(root, expression, max_report, strict_mass_rewrite, scan_diff):
    """Apply protected substitution records to one immutable committed range."""
    parts = expression.split("..")
    if len(parts) != 2:
        raise ReviewError("expected full BASE..HEAD object IDs")
    with open_reviews(root, *parts) as reviews:
        return scan_diff(reviews.diff(), {}, max_report, strict_mass_rewrite,
                         reviews=reviews)


class Reviews:
    def __init__(self, root, base, head, view: CommittedRange):
        self.root, self.base, self.head = root.resolve(), base, head
        if self.root in CATALOG.parents or self.root in RUN_BINDINGS.parents:
            raise ReviewError("authority must be outside the subject checkout")
        if not _oid(base) or not _oid(head) or len(base) != len(head):
            raise ReviewError("reviewed mode requires two full commit object IDs")
        self.view = view
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
        return self.view.diff()

    # spec: scan-corruption-reviewed-lifecycle-01
    def check_current(self):
        now = datetime.now(timezone.utc)
        if (
            not self.start <= now < self.end
            or any(not grant.start <= now < grant.end for grant in self.used.values())
            or read_protected(self.binding_path) != self.binding_bytes
            or hashlib.sha256(read_protected(CATALOG)).hexdigest() != self.digest
        ):
            raise ReviewError("binding or reviewed transition expired or was withdrawn")

    # spec: scan-corruption-reviewed-exact-01
    def match(self, path, line):
        if not _path(path):
            return None
        if path not in self.blobs:
            self.blobs[path] = (
                _blob(self.view, self.base, path),
                _blob(self.view, self.head, path),
            )
        before, after = self.blobs[path]
        grant = self.grants.get((self.subject, path, before, after, line))
        now = datetime.now(timezone.utc)
        if grant is not None and grant.start <= now < grant.end:
            self.used[grant.identity] = grant
            return grant.identity
        return None
