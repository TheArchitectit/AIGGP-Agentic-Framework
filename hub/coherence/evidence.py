# // spec: coh-ev-02, coh-ev-03, coh-ev-06
"""Evidence bundle: minimum-disclosure capture, redaction, sealing, manifest
digest. Sealed in bounded scratch, exported atomically.
"""
import json
from pathlib import Path

from . import canon


class EvidenceError(RuntimeError):
    """Evidence sealing failure (exit-33 class)."""


def seal(findings: list, output_dir: str) -> str:
    """Seal evidence for each finding; return the evidence manifest digest.

    Minimum disclosure (coh-ev-06): evidence stores only the assertion id,
    finding key, locations, expected/observed — never full source payloads.
    """
    out = Path(output_dir)
    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise EvidenceError(f"cannot create evidence directory {output_dir}: {e}") from e
    objects = []
    for f in findings:
        ev = {
            "assertion_id": f["assertion_id"],
            "finding_key": f["finding_key"],
            "subject_locations": f["subject_locations"],
            "expected": f["expected"],
            "observed": f["observed"],
        }
        payload = canon.canon(ev)
        digest = canon.digest_bytes("evidence-manifest/v1", payload)
        rel = f"evidence/findings/{f['assertion_id']}.json"
        try:
            (out / rel).parent.mkdir(parents=True, exist_ok=True)
            (out / rel).write_bytes(payload)
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
        (out / "evidence-manifest.json").write_bytes(canon.canon(manifest))
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
        fp = out / obj["path"]
        if not fp.exists():
            return False
        if canon.digest_bytes("evidence-manifest/v1", fp.read_bytes()) != obj["digest"]:
            return False
    actual = canon.digest_obj("evidence-manifest/v1", manifest)
    return actual == expected_manifest_digest
