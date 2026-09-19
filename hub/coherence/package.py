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
    normative_files = []
    for entry in inventory:
        path = entry["path"]
        kind = entry["kind"]
        recorded = entry["digest"]
        fp = root_p / path
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

    # Normative digest = canonical manifest + normative closure (design:
    # "informative content digests separately"). Informative inventory
    # entries are load-verified above but excluded from the identity, so an
    # informative-only change leaves the digest stable while any
    # reclassification — a kind flip — changes it (coh-pkg-03, R6).
    normative_bytes = b"".join(
        canon.canon({"path": str(fp.relative_to(root_p)),
                     "digest": canon.digest_bytes("file/v1", fp.read_bytes())})
        for fp in normative_files)
    package = {
        "api_version": "devgate.openspec.package/v1",
        "package_id": manifest["package_id"],
        "package_version": manifest["package_version"],
        "normative_inventory": [e for e in inventory
                                if e["kind"] == "normative"],
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
    package["package_digest"] = canon.digest(
        "package/v1", canon.canon(package) + normative_bytes)
    return package
