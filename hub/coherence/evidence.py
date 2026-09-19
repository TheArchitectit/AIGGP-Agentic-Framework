# // spec: coh-ev-02, coh-ev-03, coh-ev-06, coh-rt-07, coh-rt-04
"""Evidence bundle: minimum-disclosure capture, redaction, sealing, manifest
digest. Every artifact is written atomically: fsync to a same-directory temp
file, then rename onto the canonical path (coh-rt-07 — a canonical path never
holds partial bytes; a partial temp fragment is never a decision). Granted
secret values are redacted before sealing (coh-rt-04); an unredacted secret in
sealed evidence is an evidence ERROR, never a silent seal.

One file per finding, and every path inside the bundle: the engine emits
zero-or-many findings per assertion (design.md section 8), so naming objects by
assertion id alone would let each finding after the first overwrite the
previous bytes while keeping its own digest, and `verify` would then reject a
legitimately sealed bundle. Both the id that names a file and the manifest path
read back from disk are boundary inputs and are bounded here.
"""
import json
import re
from pathlib import Path

from . import canon, result

# The assertion-id grammar frozen in assertion.schema.json:10, now enforced at
# planning (plan._check_assertion loads that schema). This is the last gate
# before any write: seal() is also reachable directly, so the shape it derives
# a filename from is re-checked here rather than relying on every caller having
# planned first.
_ASSERTION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
# Hex chars of an object's own digest used to name its file: content-derived,
# so stable across repeats and independent of finding order.
_NAME_DIGIT_CHARS = 16


class EvidenceError(RuntimeError):
    """Evidence sealing failure (exit-33 class)."""


def contained(out: Path, rel) -> Path:
    """Resolve a bundle-relative artifact path, refusing anything landing
    outside the bundle (exit-33 class on violation).

    Both directions cross a boundary: `seal` builds the name from a
    repository-declared assertion id, `verify` reads a `path` field out of a
    manifest a tamperer may have edited. resolve() collapses `..` and follows
    symlinks, so neither can name a file beyond the run directory. Other
    bundle consumers that trust a manifest path (store.upload) must go
    through this one gate — the containment rule is per-bundle, not per-module.
    """
    if not isinstance(rel, str) or not rel:
        raise EvidenceError("evidence-path-malformed")
    root = out.resolve()
    p = (out / rel).resolve()
    if root not in p.parents:
        raise EvidenceError(f"evidence-path-out-of-bounds:{rel}")
    return p


def redact_values(obj, values: list):
    """Scrub every occurrence of each granted secret value from strings
    anywhere in the structure (module-level so the fail-safe is testable)."""
    if isinstance(obj, str):
        for r in values:
            obj = obj.replace(r, "[REDACTED]")
        return obj
    if isinstance(obj, list):
        return [redact_values(v, values) for v in obj]
    if isinstance(obj, dict):
        return {k: redact_values(v, values) for k, v in obj.items()}
    return obj


def seal(findings: list, output_dir: str, redact: list = None,
         retention_by_aid: dict = None) -> str:
    """Seal evidence for each finding; return the evidence manifest digest.

    Minimum disclosure (coh-ev-06): evidence stores only the assertion id,
    finding key, locations, expected/observed — never full source payloads.
    `redact` lists granted secret values (coh-rt-04): each is scrubbed before
    sealing, and the payload is re-checked so a scrub bypass is an evidence
    error rather than a sealed secret.

    `retention_by_aid` maps each assertion id to the days its declared
    `evidence.retention_days` asked for; the object's retention_class is
    derived from it directly (no invented bucket taxonomy). An assertion
    absent from the map falls back to the pre-fix default `"standard"`, so a
    caller that has not loaded the plan still seals a schema-valid bundle.
    """
    out = Path(output_dir)
    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise EvidenceError(f"cannot create evidence directory {output_dir}: {e}") from e
    values = [r for r in (redact or []) if isinstance(r, str) and r]
    ret_map = dict(retention_by_aid or {})
    for aid, days in ret_map.items():
        if not isinstance(days, int) or days < 0:
            raise EvidenceError(
                f"retention-days-must-be-a-non-negative-integer:{aid}={days!r}")
    objects = []
    for f in findings:
        aid = f["assertion_id"]
        if not isinstance(aid, str) or not _ASSERTION_ID_RE.fullmatch(aid):
            raise EvidenceError(f"bad-assertion-id:{aid!r}")
        days = ret_map.get(aid)
        cls = f"retention:{days}d" if isinstance(days, int) else "standard"
        ev = {
            "assertion_id": aid,
            "finding_key": f["finding_key"],
            "subject_locations": f["subject_locations"],
            "expected": f["expected"],
            "observed": f["observed"],
        }
        ev = redact_values(ev, values)
        payload = canon.canon(ev)
        # Fail-safe (coh-rt-04): the THEN clause makes an unredacted secret in
        # sealed evidence an evidence error — never a silent seal.
        if any(r in payload.decode("utf-8") for r in values):
            raise EvidenceError("unredacted-secret-in-sealed-evidence")
        digest = canon.digest_bytes("evidence-manifest/v1", payload)
        # The digest suffix is what makes one-file-per-finding hold: two
        # findings of one assertion differ in content, so they differ in name.
        rel = f"evidence/findings/{aid}--{digest[7:7 + _NAME_DIGIT_CHARS]}.json"
        contained(out, rel)
        try:
            result.emit(str(out / rel), payload)
        except OSError as e:
            raise EvidenceError(f"cannot seal evidence {rel}: {e}") from e
        objects.append({
            "path": rel, "digest": digest, "media_type": "application/json",
            "assertion_id": f["assertion_id"], "retention_class": cls,
            "redacted": True,
        })
        f["evidence_refs"] = [rel]

    manifest = {"api_version": "devgate.spec-coherence.evidence/v1", "objects": objects}
    manifest_digest = canon.digest_obj("evidence-manifest/v1", manifest)
    # The manifest write is inside the bounded path too (r3-indep item 1):
    # with zero findings — the common fully-PASS shape — this was the ONLY
    # seal write, and it escaped unwrapped as exit 1 + PermissionError.
    try:
        result.emit(str(out / "evidence-manifest.json"), canon.canon(manifest))
    except OSError as e:
        raise EvidenceError(f"cannot seal evidence manifest: {e}") from e
    return manifest_digest


def verify(output_dir: str, expected_manifest_digest: str) -> bool:
    """Verify a sealed bundle: recompute every object's digest against the
    manifest, then the manifest digest against the expected value. Detects
    tamper of both individual evidence files and the manifest itself."""
    out = Path(output_dir)
    manifest_path = out / "evidence-manifest.json"
    if not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    for obj in manifest.get("objects", []):
        # The manifest path is attacker-influenceable; a path that escapes the
        # bundle is a verification failure, never a window to read outside it
        # (verify's boolean is otherwise a content-matches-digest oracle).
        try:
            fp = contained(out, obj.get("path"))
        except EvidenceError:
            return False
        if not fp.is_file():
            return False
        if canon.digest_bytes("evidence-manifest/v1", fp.read_bytes()) != obj["digest"]:
            return False
    actual = canon.digest_obj("evidence-manifest/v1", manifest)
    return actual == expected_manifest_digest
