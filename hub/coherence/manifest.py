# // spec: coh-id-02
"""Subject manifest: normalized relative paths, raw-byte SHA-256, explicit
policy outcomes for non-file entries, traversal/collision rejection, and
read-time re-verification. Deterministic traversal (sorted).
"""
import hashlib
import os
import unicodedata
from pathlib import Path

from . import canon


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


def _digest_file(fp: Path) -> str:
    h = hashlib.sha256()
    with open(fp, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return canon.digest_bytes("file/v1", h.digest())


def build(root: str, subject_kind: str = "source-tree") -> dict:
    """Build the immutable subject manifest for a directory tree."""
    root_p = Path(root).resolve()
    if not root_p.is_dir():
        raise SubjectError(f"subject root is not a directory: {root!r}")

    entries = []
    seen_paths = {}
    for dirpath, dirnames, filenames in os.walk(root_p):
        dirnames.sort()
        for name in sorted(filenames):
            fp = Path(dirpath) / name
            rel = _norm(str(fp.relative_to(root_p)))
            _check_safe(rel, root_p)
            # Case/Unicode collision detection on the normalized key.
            key = rel.casefold()
            if key in seen_paths:
                raise SubjectError(
                    f"path normalization collision: {rel!r} vs {seen_paths[key]!r}")
            seen_paths[key] = rel
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
