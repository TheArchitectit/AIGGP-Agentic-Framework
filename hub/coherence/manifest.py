# // spec: coh-id-02, coh-sec-01, coh-3d-01, coh-3d-04
"""Subject manifest: normalized relative paths, raw-byte SHA-256, explicit
policy outcomes for non-file entries, traversal/collision rejection, and
read-time re-verification. Deterministic traversal (sorted).
"""
import hashlib
import json
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


def check_safe(rel: str, root: Path) -> None:
    """Contain a repository-supplied path under `root` (coh-sec-01).

    Public because the containment contract is not manifest-specific: the
    evaluation context's captured-fact ids and the evidence manifest's object
    paths are the same class of input and use the same three layers
    (absolute / segment / resolved-containment). Raises SubjectError, whose
    message names the offending path and never quotes target content.
    """
    if rel.startswith("/") or rel.startswith("~"):
        raise SubjectError(f"absolute path not allowed: {rel!r}")
    if "\x00" in rel:
        raise SubjectError(f"embedded NUL in path: {rel!r}")
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise SubjectError(f"path traversal or empty segment: {rel!r}")
    # Resolve and confirm containment. A missing target still resolves
    # (non-strict), so this answers "may it be read", not "does it exist".
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


def _digest_and_size(fp: Path) -> tuple:
    """Digest and byte size from ONE streaming read.

    Audit finding F11: the manifest used to read each file twice — size from
    `read_bytes()`, digest from a second pass — so a mutation between the
    reads produced an entry whose size and digest described different
    content. Both values must come from the same bytes."""
    h = hashlib.sha256()
    size = 0
    with open(fp, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
            size += len(chunk)
    return canon.digest_bytes("file/v1", h.digest()), size


DEFAULT_EXCLUDES = (".git", "node_modules", "__pycache__", ".venv", "venv",
                    "dist", "build", "target")

WORLD_BUNDLE_FILE = "world-bundle.json"
PART_KINDS = ("world-ir", "glb", "engine-scene", "executable-build",
              "capture", "evaluation-record")


def _build_world_parts(root_p: Path, entry_by_path: dict) -> list:
    """Resolve and verify composite 3D world-bundle parts (coh-3d-01, coh-3d-04).

    `world-bundle.json` at the subject root declares the composite parts by
    relative path (and for `capture` parts, a `capture_config_path` pointing to
    the pinned capture configuration). Every part digest is verified from the
    walked file entries so any 1-byte mutation to any part or capture config
    alters `parts` and therefore `subject_digest`.
    """
    desc_path = root_p / WORLD_BUNDLE_FILE
    if WORLD_BUNDLE_FILE not in entry_by_path or not desc_path.is_file():
        raise SubjectError(
            "world-bundle subject requires world-bundle.json at subject root")
    try:
        doc = json.loads(desc_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SubjectError(f"invalid world-bundle.json: {e}") from None
    if not isinstance(doc, dict):
        raise SubjectError("world-bundle.json must be a JSON object")
    raw_parts = doc.get("parts")
    if not isinstance(raw_parts, list) or not raw_parts:
        raise SubjectError("world-bundle.json parts must be a non-empty array")

    seen_ids = set()
    parts = []
    for raw in raw_parts:
        if not isinstance(raw, dict):
            raise SubjectError("world-bundle part entry must be an object")
        pid = raw.get("part_id")
        kind = raw.get("kind")
        rel = raw.get("path")
        if not isinstance(pid, str) or not pid.strip():
            raise SubjectError("world-bundle part missing non-empty part_id")
        if pid in seen_ids:
            raise SubjectError(f"duplicate world-bundle part_id: {pid!r}")
        seen_ids.add(pid)
        if kind not in PART_KINDS:
            raise SubjectError(f"unsupported world-bundle part kind: {kind!r}")
        if not isinstance(rel, str) or not rel:
            raise SubjectError(f"world-bundle part {pid!r} missing path")
        norm_rel = _norm(rel)
        check_safe(norm_rel, root_p)
        ent = entry_by_path.get(norm_rel)
        if ent is None or ent.get("kind") != "file" or not ent.get("digest"):
            raise SubjectError(
                f"world-bundle part {pid!r} path is missing or non-regular: "
                f"{norm_rel!r}")
        part_obj = {
            "part_id": pid,
            "kind": kind,
            "digest": ent["digest"],
        }
        cfg_rel = raw.get("capture_config_path")
        if kind == "capture":
            if not isinstance(cfg_rel, str) or not cfg_rel:
                raise SubjectError(
                    f"capture part {pid!r} requires capture_config_path "
                    f"(coh-3d-04)")
            norm_cfg = _norm(cfg_rel)
            check_safe(norm_cfg, root_p)
            cfg_ent = entry_by_path.get(norm_cfg)
            if (cfg_ent is None or cfg_ent.get("kind") != "file"
                    or not cfg_ent.get("digest")):
                raise SubjectError(
                    f"capture part {pid!r} config is missing or non-regular: "
                    f"{norm_cfg!r}")
            part_obj["capture_config_digest"] = cfg_ent["digest"]
        elif cfg_rel is not None:
            raise SubjectError(
                f"non-capture part {pid!r} may not declare capture_config_path")
        parts.append(part_obj)

    parts.sort(key=lambda p: (p["kind"], p["part_id"]))
    return parts


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
            check_safe(rel, root_p)
            _check_collision(seen_paths, rel)
            if fp.is_symlink():
                entries.append({
                    "path": rel, "kind": "symlink", "digest": None,
                    "policy_outcome": "symlink-forbidden", "size_bytes": None,
                })
                continue
            digest, size = _digest_and_size(fp)
            entries.append({
                "path": rel, "kind": "file", "digest": digest,
                "policy_outcome": None, "size_bytes": size,
            })

    manifest = {
        "api_version": "devgate.spec-coherence.subject-manifest/v1",
        "subject_kind": subject_kind,
        "entries": entries,
    }
    if subject_kind == "world-bundle":
        entry_by_path = {e["path"]: e for e in entries}
        manifest["parts"] = _build_world_parts(root_p, entry_by_path)
    manifest["subject_digest"] = canon.digest_obj("subject-manifest/v1", manifest)
    return manifest


def verify_read(fp: Path, expected_digest: str) -> None:
    """Read-time re-verification: mutation mid-run is ERROR (coh-id-02)."""
    actual = _digest_file(fp)
    if actual != expected_digest:
        raise SubjectError(
            f"input mutated during evaluation: {fp.name} "
            f"expected {expected_digest}, read {actual}")


def first_mutation(snapshot: dict, root: str):
    """First path that drifted from a closed snapshot, or None (coh-id-02).

    The snapshot is a manifest.build() result; `root` is re-walked under the
    SAME rules, so replacement, deletion, and untracked additions all name a
    path, while a mutation that makes the tree unbuildable (a collision the
    original walk refused) cannot escape as a traceback — it names the tree.
    Deterministic: entries are compared in walk order, so retries of the same
    mutated tree yield the same reason string.
    """
    try:
        current = build(root, snapshot.get("subject_kind", "source-tree"))
    except SubjectError:
        return "<tree-unbuildable>"
    # The recorded tuple includes policy_outcome deliberately: symlink and
    # submodule entries carry a null digest (coh-id-02's schema freezes
    # that), so without the policy field a forbidden->escape flip or a
    # submodule re-pin would diff clean.
    fields = ("path", "kind", "digest", "policy_outcome")
    key = lambda e: tuple(e.get(f) for f in fields)
    old = {key(e) for e in snapshot["entries"]}
    new = {key(e) for e in current["entries"]}
    for e in snapshot["entries"]:
        if key(e) not in new:
            return e["path"]
    for e in current["entries"]:
        if key(e) not in old:
            return e["path"]
    return None
