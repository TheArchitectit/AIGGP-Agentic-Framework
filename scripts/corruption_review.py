#!/usr/bin/env python3
# spec: fw-corruption-02
"""Load detached, authority-digested reviews for exact committed ranges."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


API_VERSION = "devgate.corruption-range-review/v1"
_REPO_ID = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_HEX = re.compile(r"^[0-9a-f]+$")


class ReviewError(ValueError):
    """Explicit review configuration is malformed or not safely readable."""


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args],
                            capture_output=True, text=True)
    if result.returncode:
        raise ReviewError(f"git {' '.join(args[:2])} failed")
    return result.stdout.strip()


def _unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ReviewError(f"duplicate review key: {key}")
        out[key] = value
    return out


def _origin_repository(root: Path) -> str:
    """Read origin identity without ever returning its credential-bearing URL."""
    result = subprocess.run(["git", "-C", str(root), "remote", "get-url", "origin"],
                            capture_output=True, text=True)
    if result.returncode:
        raise ReviewError("cannot verify repository identity from GITHUB_REPOSITORY or origin")
    value = result.stdout.strip()
    if "://" not in value:
        match = re.fullmatch(r"(?:[^@/]+@)?github\.com:(.+)", value)
        if not match:
            raise ReviewError("origin is not a canonical GitHub repository")
        path = match.group(1)
    else:
        parsed = urlsplit(value)
        if parsed.hostname != "github.com" or parsed.query or parsed.fragment:
            raise ReviewError("origin is not a canonical GitHub repository")
        path = parsed.path.lstrip("/")
    path = path.strip("/").removesuffix(".git")
    if not _REPO_ID.fullmatch(path):
        raise ReviewError("origin is not a canonical GitHub OWNER/REPO")
    return path


def committed_range(root: Path, expression: str, repository_id: str) -> dict:
    """Validate and identify a literal full-SHA BASE..HEAD range."""
    if not _REPO_ID.fullmatch(repository_id):
        raise ReviewError("repository identity must be OWNER/REPO")
    context_repository = os.environ.get("GITHUB_REPOSITORY")
    actual_repository = context_repository or _origin_repository(root)
    if not _REPO_ID.fullmatch(actual_repository) or actual_repository.casefold() != repository_id.casefold():
        raise ReviewError("repository identity does not match the scanned target")
    fmt = _git(root, "rev-parse", "--show-object-format")
    width = 64 if fmt == "sha256" else 40 if fmt == "sha1" else 0
    if not width:
        raise ReviewError("unsupported Git object format")
    match = re.fullmatch(rf"([0-9a-f]{{{width}}})\.\.HEAD", expression or "")
    if not match:
        raise ReviewError("exact-review mode requires FULL_BASE_SHA..HEAD")
    base = match.group(1)
    head = _git(root, "rev-parse", "--verify", "HEAD^{commit}")
    base_commit = _git(root, "rev-parse", "--verify", f"{base}^{{commit}}")
    if base_commit != base:
        raise ReviewError("range base is not a canonical full commit ID")
    action_sha = os.environ.get("GITHUB_SHA")
    if action_sha:
        if not re.fullmatch(rf"[0-9a-f]{{{width}}}", action_sha):
            raise ReviewError("GITHUB_SHA is not a full canonical commit ID")
        if _git(root, "rev-parse", "--verify", f"{action_sha}^{{commit}}") != head:
            raise ReviewError("resolved HEAD does not match the GitHub Actions run SHA")
    ancestor = subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor",
                               base, head], capture_output=True)
    if ancestor.returncode != 0:
        raise ReviewError("range base is not an ancestor of HEAD")
    tree = _git(root, "rev-parse", "--verify", f"{head}^{{tree}}")
    return {"repository": repository_id, "base_commit": base,
            "head_commit": head, "target_tree": tree,
            "diff_range": f"{base}..{head}"}


def load_review(root: Path, file_name: str, expected_sha256: str,
                identity: dict) -> tuple[dict | None, str]:
    """Return a binding-matched review, or None for a valid stale receipt."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256 or ""):
        raise ReviewError("review SHA-256 must be 64 lowercase hex characters")
    path = Path(file_name)
    if not path.is_absolute():
        raise ReviewError("review file path must be absolute")
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ReviewError("review file path must not contain symlinks")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ReviewError("review file cannot be resolved") from exc
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        pass
    else:
        raise ReviewError("review file must be outside the scanned repository")
    if not resolved.is_file() or resolved.stat().st_size > 65536:
        raise ReviewError("review file must be a regular file no larger than 64 KiB")
    try:
        raw = resolved.read_bytes()
    except OSError as exc:
        raise ReviewError("review file cannot be read") from exc
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ReviewError("review file does not match the authority SHA-256")
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewError("review file is not valid UTF-8 JSON") from exc
    if not isinstance(doc, dict) or doc.get("api_version") != API_VERSION:
        raise ReviewError("unsupported review API version")
    required = {"api_version", "review_id", "repository", "base_commit",
                "target_tree", "inventory"}
    if set(doc) != required or not isinstance(doc["review_id"], str) or not doc["review_id"].strip():
        raise ReviewError("review document has missing or unknown fields")
    if not isinstance(doc["repository"], str) or not _REPO_ID.fullmatch(doc["repository"]):
        raise ReviewError("review repository is malformed")
    for key in ("base_commit", "target_tree"):
        if not isinstance(doc[key], str) or not _HEX.fullmatch(doc[key]):
            raise ReviewError(f"review {key} is malformed")
    object_width = len(identity["head_commit"])
    if len(doc["base_commit"]) != object_width or len(doc["target_tree"]) != object_width:
        raise ReviewError("review commit and tree IDs do not match repository object format")
    if not isinstance(doc["inventory"], dict):
        raise ReviewError("review inventory must be an object")
    inv = doc["inventory"]
    if set(inv) != {"flips", "mass_rewrites", "bulk_mutation",
                    "strict_mass_rewrite", "failures", "warnings"}:
        raise ReviewError("review inventory has missing or unknown fields")
    if (not isinstance(inv["flips"], list)
            or any(not isinstance(x, str) for x in inv["flips"])
            or inv["flips"] != sorted(set(inv["flips"]))
            or not isinstance(inv["failures"], list)
            or any(not isinstance(x, str) for x in inv["failures"])
            or inv["failures"] != sorted(set(inv["failures"]))
            or not isinstance(inv["warnings"], list)
            or any(not isinstance(x, str) for x in inv["warnings"])
            or inv["warnings"] != sorted(set(inv["warnings"]))
            or not isinstance(inv["strict_mass_rewrite"], bool)
            or not isinstance(inv["mass_rewrites"], list)
            or any(not isinstance(x, dict) or set(x) != {"path", "added", "removed"}
                   or not isinstance(x["path"], str)
                   or type(x["added"]) is not int or type(x["removed"]) is not int
                   for x in inv["mass_rewrites"])):
        raise ReviewError("review finding inventory is malformed")
    paths = [row["path"] for row in inv["mass_rewrites"]]
    if paths != sorted(set(paths)) or any(row["added"] < 1 or row["removed"] < 1
                                          for row in inv["mass_rewrites"]):
        raise ReviewError("review mass-rewrite paths or counts are malformed")
    bulk = inv["bulk_mutation"]
    if bulk is not None and (not isinstance(bulk, dict)
                             or set(bulk) != {"files", "threshold"}
                             or type(bulk["files"]) is not int
                             or type(bulk["threshold"]) is not int
                             or bulk["files"] < 1 or bulk["threshold"] < 1
                             or bulk["files"] < bulk["threshold"]):
        raise ReviewError("review bulk-mutation inventory is malformed")
    for key in ("repository", "base_commit", "target_tree"):
        if doc[key] != identity["target_tree" if key == "target_tree" else key]:
            return None, f"detached review does not match {key.replace('_', ' ')}"
    return doc, "detached review identity matches"


def prepare_review(root: Path, expression: str, repository_id: str,
                   file_name: str | None, expected_sha256: str | None) -> tuple[dict | None, str, str]:
    identity = committed_range(root, expression, repository_id)
    if file_name is None:
        return None, "exact range mode active without a detached review", identity["diff_range"]
    if expected_sha256 is None:
        raise ReviewError("detached review SHA-256 is missing")
    review, status = load_review(root, file_name, expected_sha256, identity)
    return review, status, identity["diff_range"]
