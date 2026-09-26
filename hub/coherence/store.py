# // spec: coh-ev-02
"""Evidence store adapter (coh-ev-02, design.md section 9): a sealed run is an
offline local bundle; a remote upload runs AFTER sealing and is retryable,
re-sending the exact bytes that were sealed.

The service never opens a network path itself — TestStaticDefaultDeny forbids
importing any network module in hub/coherence — so `upload` is handed a
transport callable. With no transport configured the bundle simply stays local
(design.md:251 "normal evaluation has no online dependency"). Whatever the
transport, the bytes it receives are the sealed bytes: the canonical decision
and evidence-manifest digests are fixed at seal and an upload attempt never
rewrites them (coh-ev-02's retry scenario).
"""
import json
from pathlib import Path

from . import canon, evidence


class UploadError(RuntimeError):
    """Remote upload failed; the sealed bundle is untouched and may be re-sent."""


# Artifacts that constitute a sealed bundle, in the order a consumer reads
# them: decision, then attestation (when signed), then manifest and evidence
# objects. attest.verify's required set must stay in sync — the audit pins
# this coupling.
_BUNDLE_FILES = ("result.json", "attestation.json", "evidence-manifest.json")


def artifacts(run_dir) -> list:
    """The bundle artifacts present on disk, as Paths under run_dir.

    The manifest enumerates evidence objects by a `path` field a tamperer can
    edit after seal — `evidence.contained` is the one gate that decides what
    "inside the bundle" means, and store.upload must route through it the
    same way evidence.verify does (round-9 finding, applied here by the
    fresh-eyes audit). A malformed or escaping path raises UploadError: the
    store never hands out-of-bounds bytes to a transport.
    """
    out = Path(run_dir)
    found = [out / name for name in _BUNDLE_FILES if (out / name).is_file()]
    manifest_path = out / "evidence-manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for obj in manifest.get("objects", []):
            try:
                fp = evidence.contained(out, obj.get("path"))
            except evidence.EvidenceError as e:
                raise UploadError(str(e)) from e
            if fp.is_file():
                found.append(fp)
    return found


def upload(run_dir: str, transport) -> dict:
    """Send every bundle artifact through `transport(name, payload)`.

    `name` is the bundle-relative path (the artifact's identity), `payload`
    its sealed bytes. Any transport exception is surfaced as UploadError — the
    caller retries later against the same sealed bundle. Returns the digests
    it uploaded, so the caller can compare on retry to prove nothing shifted.
    """
    out = Path(run_dir)
    if not (out / "evidence-manifest.json").is_file():
        raise UploadError("cannot upload an unsealed bundle")
    for fp in artifacts(out):
        try:
            transport(fp.relative_to(out).as_posix(), fp.read_bytes())
        except UploadError:
            raise
        except OSError as e:
            raise UploadError(f"upload-failed:{fp.name}:{e}") from e
    return {"evidence_manifest_digest": manifest_digest(run_dir)}


def manifest_digest(run_dir: str) -> str:
    """Recompute the sealed evidence-manifest digest from disk."""
    manifest = json.loads((Path(run_dir) / "evidence-manifest.json").read_text(encoding="utf-8"))
    return canon.digest_obj("evidence-manifest/v1", manifest)
