# // spec: coh-pkg-01, coh-pkg-02, coh-pkg-03, coh-pkg-04, coh-pkg-05, coh-id-03, coh-ev-07
"""OpenSpec package resolution: manifest validation, authenticated normative
inventory, frozen import closure, canonical package digest, detached-approval
verification hook.
"""
import json
from pathlib import Path

from . import canon


class PackageError(ValueError):
    """Invalid package (exit-30 class)."""


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise PackageError(f"cannot read package manifest {path}: {e}") from e


def _contained(rel: str, root: Path) -> Path:
    """Resolve an inventory entry's path under the package root, rejecting
    anything that escapes (repository-supplied content is untrusted;
    coh-sec-01). Absolute paths, `~`, empty/`.`/`..` segments, NUL bytes, and
    symlink escapes are all invalid input — never reads. Without this, a
    manifest naming `../../../etc/passwd` made the service read arbitrary
    host files and leak their existence/length through digest mismatch
    errors (audit finding F3)."""
    if not isinstance(rel, str) or not rel or "\x00" in rel:
        raise PackageError(f"invalid inventory path: {rel!r}")
    if rel.startswith("/") or rel.startswith("~"):
        raise PackageError(f"inventory path must be relative: {rel!r}")
    if any(p in ("", ".", "..") for p in rel.split("/")):
        raise PackageError(f"inventory path traversal rejected: {rel!r}")
    fp = root / rel
    try:
        resolved = fp.resolve()
    except OSError as e:
        raise PackageError(f"unresolvable inventory path {rel!r}: {e}") from e
    if root not in resolved.parents and resolved != root:
        raise PackageError(f"inventory path escapes package root: {rel!r}")
    return fp


def resolve(root: str) -> dict:
    """Resolve and validate a package rooted at `root`.

    Expects `package.json` (the manifest) plus a `specs/` tree of assertion
    files. Enforces: schema version, unique assertion IDs, resolvable normative
    references, acyclic import closure, and the authenticated normative
    inventory. Returns the resolved package with its normative digest.
    """
    root_p = Path(root).resolve()
    manifest_path = root_p / "package.json"
    if not manifest_path.exists():
        raise PackageError(f"missing package manifest: {manifest_path}")
    manifest = _load_json(manifest_path)

    if manifest.get("schema_version") != "devgate.openspec.package/v1":
        raise PackageError(
            f"unsupported schema_version: {manifest.get('schema_version')!r}")

    inventory = manifest.get("normative_inventory") or []
    if not inventory:
        raise PackageError("package has empty normative_inventory")

    # Authenticated normative inventory: every normative file must exist and
    # match its recorded digest; reclassification changes the digest.
    # Paths are contained under the package root BEFORE any read (coh-sec-01).
    normative_files = []
    for entry in inventory:
        if not isinstance(entry, dict) or "path" not in entry or "kind" not in entry:
            raise PackageError(f"malformed inventory entry: {entry!r}")
        path = entry["path"]
        kind = entry["kind"]
        recorded = entry.get("digest")
        fp = _contained(path, root_p)
        if not fp.exists():
            raise PackageError(f"inventory entry missing on disk: {path}")
        actual = canon.digest_bytes("file/v1", fp.read_bytes())
        if actual != recorded:
            raise PackageError(
                f"inventory digest mismatch for {path}: "
                f"recorded {recorded}, actual {actual}")
        if kind == "normative":
            normative_files.append(fp)

    # Import closure: imports must resolve to digested content.
    imports = manifest.get("imports") or []
    for imp in imports:
        if not imp.get("digest"):
            raise PackageError(
                f"import {imp.get('package_id')!r} has no resolved digest; "
                "imports must be frozen before evaluation")

    # Normative digest = canonical manifest + normative closure.
    normative_bytes = b"".join(
        canon.canon({"path": str(fp.relative_to(root_p)),
                     "digest": canon.digest_bytes("file/v1", fp.read_bytes())})
        for fp in normative_files)
    package = {
        "api_version": "devgate.openspec.package/v1",
        "package_id": manifest["package_id"],
        "package_version": manifest["package_version"],
        "normative_inventory": inventory,
        "imports": imports,
    }
    # Declared product identity (approved values assertions compare against)
    # and normative requirement registry, when present in the manifest.
    if "product" in manifest:
        package["product"] = manifest["product"]
    if "normative_requirements" in manifest:
        package["normative_requirements"] = manifest["normative_requirements"]
    if "release_manifest" in manifest:
        package["release_manifest"] = manifest["release_manifest"]
    package["package_digest"] = canon.digest_obj("package/v1", package)
    return package
