# // spec: coh-ev-02, coh-ev-03, coh-ev-06, coh-rt-07, coh-rt-04
"""Evidence bundle: minimum-disclosure capture, redaction, sealing, manifest
digest. Every artifact is written atomically: fsync to a same-directory temp
file, then rename onto the canonical path (coh-rt-07 — a canonical path never
holds partial bytes; a partial temp fragment is never a decision). Granted
secret values are redacted before sealing (coh-rt-04); an unredacted secret in
sealed evidence is an evidence ERROR, never a silent seal.
"""
import json
import os
from pathlib import Path

from . import canon, result


class EvidenceError(RuntimeError):
    """Evidence sealing failure (exit-33 class)."""


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


def seal(findings: list, output_dir: str, redact: list = None) -> str:
    """Seal evidence for each finding; return the evidence manifest digest.

    Minimum disclosure (coh-ev-06): evidence stores only the assertion id,
    finding key, locations, expected/observed — never full source payloads.
    `redact` lists granted secret values (coh-rt-04): each is scrubbed before
    sealing, and the payload is re-checked so a scrub bypass is an evidence
    error rather than a sealed secret.
    """
    out = Path(output_dir)
    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise EvidenceError(f"cannot create evidence directory {output_dir}: {e}") from e
    values = [r for r in (redact or []) if isinstance(r, str) and r]
    objects = []
    for f in findings:
        ev = {
            "assertion_id": f["assertion_id"],
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
        rel = f"evidence/findings/{f['assertion_id']}.json"
        try:
            result.emit(str(out / rel), payload)
        except OSError as e:
            raise EvidenceError(f"cannot seal evidence {rel}: {e}") from e
        objects.append({
            "path": rel, "digest": digest, "media_type": "application/json",
            "assertion_id": f["assertion_id"], "retention_class": "standard",
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
    tamper of both individual evidence files and the manifest itself.

    Fail-closed (fw-ev-01): any malformed manifest shape — objects that is not
    a list, an entry that is not an object with string path/digest fields —
    is a rejected bundle (False), never a crash. A tamper detector that can
    be crashed by crafted input is a denial-of-service on the verification
    path itself.
    """
    out = Path(output_dir)
    manifest_path = out / "evidence-manifest.json"
    if not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(manifest, dict):
        return False
    objects = manifest.get("objects")
    if not isinstance(objects, list):
        return False
    for obj in objects:
        if not isinstance(obj, dict):
            return False
        rel, digest = obj.get("path"), obj.get("digest")
        if not isinstance(rel, str) or not isinstance(digest, str):
            return False
        # Sealed evidence is bundle-relative; an absolute or parent-escaping
        # path is not a bundle member (fw-ev-02) — reject, do not read.
        if os.path.isabs(rel) or os.pardir in Path(rel).parts:
            return False
        fp = out / rel
        try:
            if not fp.is_file():
                return False
            actual = canon.digest_bytes("evidence-manifest/v1", fp.read_bytes())
        except OSError:
            return False
        if actual != digest:
            return False
    try:
        actual = canon.digest_obj("evidence-manifest/v1", manifest)
    except (TypeError, ValueError):
        return False
    return actual == expected_manifest_digest
