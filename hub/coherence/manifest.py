# // spec: coh-id-02
"""Subject manifest: normalized relative paths, raw-byte SHA-256, explicit
policy outcomes for non-file entries, traversal/collision rejection, and
read-time re-verification. Deterministic traversal (sorted).
"""
import hashlib
import os
import re
import unicodedata
from pathlib import Path

from . import canon

_SHA_RE = re.compile(r"[0-9a-f]{40,64}")


class SubjectError(ValueError):
    """Invalid subject input (exit-30 class)."""


def _norm(path: str) -> str:
    # Normalize separators and NFC Unicode for the manifest representation.
    return unicodedata.normalize("NFC", path.replace("\\", "/"))


def _check_safe(rel: str, root: Path) -> None:
    if rel.startswith("/") or rel.startswith("~"):
        raise SubjectError(f"absolute path not allowed: {rel!r}")
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise SubjectError(f"path traversal or empty segment: {rel!r}")
    # Resolve and confirm containment.
    resolved = (root / rel).resolve()
    if root not in resolved.parents and resolved != root:
        raise SubjectError(f"path escapes root: {rel!r}")


def _escapes(fp: Path, root: Path) -> bool:
    """True when fp resolves outside root (used to classify symlink entries)."""
    try:
        resolved = fp.resolve()
    except OSError:
        return True
    return root not in resolved.parents and resolved != root


def _gitlink_commit(subdir: Path):
    """Resolve the pinned commit of an initialized submodule from its gitdir
    metadata: the `.git` file's `gitdir:` pointer, then HEAD (detached SHA or
    `ref:` resolved through loose refs, then packed-refs). Pure file reads —
    no git execution, deterministic. Returns None when the pin cannot be
    resolved; the entry is then recorded `submodule-unresolved` rather than
    silently claiming a pin it cannot name (round-1 partial).
    """
    try:
        raw = (subdir / ".git").read_text(errors="replace").strip()
    except OSError:
        return None
    if not raw.startswith("gitdir:"):
        return None
    target = raw[len("gitdir:"):].strip()
    gd = Path(target)
    gitdir = gd if gd.is_absolute() else (subdir / gd)
    try:
        head = (gitdir / "HEAD").read_text(errors="replace").strip()
    except OSError:
        return None
    if _SHA_RE.fullmatch(head):
        return head
    if not head.startswith("ref:"):
        return None
    ref = head[len("ref:"):].strip()
    try:
        val = (gitdir / ref).read_text(errors="replace").strip()
        if _SHA_RE.fullmatch(val):
            return val
    except OSError:
        pass
    try:
        for line in (gitdir / "packed-refs").read_text(errors="replace").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == ref and _SHA_RE.fullmatch(parts[0]):
                return parts[0]
    except OSError:
        pass
    return None


def _check_collision(seen: dict, rel: str) -> None:
    """Reject path normalization collisions (case/Unicode) (coh-id-02)."""
    key = rel.casefold()
    if key in seen:
        raise SubjectError(
            f"path normalization collision: {rel!r} vs {seen[key]!r}")
    seen[key] = rel


def _digest_file(fp: Path) -> str:
    h = hashlib.sha256()
    with open(fp, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return canon.digest_bytes("file/v1", h.digest())


DEFAULT_EXCLUDES = (".git", "node_modules", "__pycache__", ".venv", "venv",
                    "dist", "build", "target")


def build(root: str, subject_kind: str = "source-tree",
          excludes: tuple = DEFAULT_EXCLUDES) -> dict:
    """Build the immutable subject manifest for a directory tree.

    Submodules (a `.git` file in a subdirectory, i.e. a gitlink) are recorded as
    `submodule` entries with their pinned commit in policy_outcome
    (`submodule-pinned:<sha>`, or `submodule-unresolved` when the gitdir
    metadata cannot resolve it); they are never descended. Excluded
    directories (build outputs, VCS metadata, dependency trees) are recorded
    as `excluded` without digests so the manifest is explicit about what it
    did not consider (coh-id-02).
    """
    root_p = Path(root).resolve()
    if not root_p.is_dir():
        raise SubjectError(f"subject root is not a directory: {root!r}")

    entries = []
    seen_paths = {}
    for dirpath, dirnames, filenames in os.walk(root_p):
        dirnames.sort()
        # Symlinked directories are never descended (os.walk default), but they
        # must be RECORDED rather than silently vanishing: an escaping symlink
        # is a policy event, not an omission (coh-id-02, round-2 audit finding 4).
        for dname in list(dirnames):
            link = Path(dirpath) / dname
            rel = _norm(str(link.relative_to(root_p)))
            if link.is_symlink():
                _check_collision(seen_paths, rel)
                escaped = _escapes(link, root_p)
                entries.append({
                    "path": rel, "kind": "symlink", "digest": None,
                    "policy_outcome": ("symlink-escape" if escaped
                                       else "symlink-forbidden"),
                    "size_bytes": None,
                })
                dirnames.remove(dname)
                continue
            # Submodule (gitlink): a `.git` FILE inside the directory. The
            # pinned commit is captured from gitdir metadata when resolvable;
            # an unresolvable pin is recorded `submodule-unresolved` — never
            # `submodule-pinned` without naming the pin (round-1 partial).
            if (link / ".git").is_file():
                _check_collision(seen_paths, rel)
                sha = _gitlink_commit(link)
                entries.append({
                    "path": rel, "kind": "submodule", "digest": None,
                    "policy_outcome": (f"submodule-pinned:{sha}" if sha
                                       else "submodule-unresolved"),
                    "size_bytes": None,
                })
                dirnames.remove(dname)
                continue
            # Explicit exclusion: recorded, never silently skipped.
            if dname in excludes:
                _check_collision(seen_paths, rel)
                entries.append({
                    "path": rel, "kind": "excluded", "digest": None,
                    "policy_outcome": f"excluded-by-policy:{dname}",
                    "size_bytes": None,
                })
                dirnames.remove(dname)
        for name in sorted(filenames):
            fp = Path(dirpath) / name
            rel = _norm(str(fp.relative_to(root_p)))
            _check_safe(rel, root_p)
            _check_collision(seen_paths, rel)
            if fp.is_symlink():
                entries.append({
                    "path": rel, "kind": "symlink", "digest": None,
                    "policy_outcome": "symlink-forbidden", "size_bytes": None,
                })
                continue
            data = fp.read_bytes()
            entries.append({
                "path": rel, "kind": "file", "digest": _digest_file(fp),
                "policy_outcome": None, "size_bytes": len(data),
            })

    manifest = {
        "api_version": "devgate.spec-coherence.subject-manifest/v1",
        "subject_kind": subject_kind,
        "entries": entries,
    }
    manifest["subject_digest"] = canon.digest_obj("subject-manifest/v1", manifest)
    return manifest


def verify_read(fp: Path, expected_digest: str) -> None:
    """Read-time re-verification: mutation mid-run is ERROR (coh-id-02)."""
    actual = _digest_file(fp)
    if actual != expected_digest:
        raise SubjectError(
            f"input mutated during evaluation: {fp.name} "
            f"expected {expected_digest}, read {actual}")
