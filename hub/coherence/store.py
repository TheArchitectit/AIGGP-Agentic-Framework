# // spec: coh-ev-02, coh-ev-04, coh-ctx-05
"""Evidence store: immutable content-addressed objects, retryable upload,
complete decision-cache keys (S5 remainder).

IMMUTABILITY: objects are stored under their own digest and NEVER
overwritten — `put` of an existing digest verifies the bytes match and
returns the existing object; a digest collision with different content is
a hard error (either a sha256 collision or tampering with the store; both
must stop the world). This is what makes upload retries safe: a retried
upload skips objects the store already holds, verified.

OFFLINE LOCAL-BUNDLE MODE: the default adapter is a local directory —
the S5 store contract (put/get by digest, immutability) without any
network dependency, consistent with the service's default-deny posture.

COMPLETE CACHE KEY (coh-ctx-05): a cached decision may be reused only
when EVERY input matches — subject, package, policy, context, evaluator
image, plugins, captured facts, TTL, retention, AND signer. A cache key
over a subset silently reuses decisions made under different conditions;
the key here is canonically total.

RETENTION (coh-ev-04): entries carry retention metadata; a cache entry
whose retention window has closed is invalid regardless of content
identity — expiry invalidates, not just drift.
"""
import json
import os
import time
from pathlib import Path

from . import canon
from .resource_limits import backoff


class StoreError(RuntimeError):
    """Evidence-store failure (exit-33 class)."""


class LocalBundleStore:
    """Content-addressed, append-only object store on a local directory.

    Layout: <root>/objects/<digest[7:9]>/<digest> — the digest INCLUDES the
    role tag so different kinds of objects never collide.
    """

    def __init__(self, root: str):
        self.root = Path(root)
        self.objects = self.root / "objects"

    def _path_for(self, digest: str) -> Path:
        if not isinstance(digest, str) or not digest.startswith("sha256:") \
                or len(digest) != 71:
            raise StoreError(f"bad object digest: {digest!r}")
        return self.objects / digest[7:9] / digest

    def has(self, digest: str) -> bool:
        return self._path_for(digest).is_file()

    def put(self, role_tag: str, payload: bytes) -> str:
        """Store payload immutably; returns its digest.

        A digest that already exists must hold the SAME bytes: the store
        verifies before treating the write as a no-op, so a forged or
        corrupted existing object is a hard error rather than a silent
        overwrite-or-ignore.
        """
        digest = canon.digest_bytes(role_tag, payload)
        path = self._path_for(digest)
        if path.exists():
            if path.read_bytes() != payload:
                raise StoreError(
                    f"digest collision with different content: {digest}")
            return digest
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write (coh-rt-07 discipline): a partial object must never
        # sit at its content address — presence IS completeness.
        tmp = path.parent / f".{path.name}.tmp-{os.getpid()}"
        try:
            with open(tmp, "wb") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
            # Role-tag sidecar: digests are domain-separated by role, so
            # read-back verification needs the tag recorded at write time.
            (path.parent / f"{digest}.role").write_text(role_tag)
        except OSError as e:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise StoreError(f"cannot store object {digest}: {e}") from e
        return digest

    def get(self, digest: str) -> bytes:
        path = self._path_for(digest)
        try:
            payload = path.read_bytes()
            role_tag = (path.parent / f"{digest}.role").read_text().strip()
        except OSError as e:
            raise StoreError(f"object not found: {digest}") from e
        # Read-back verification: the address is the claim; the bytes must
        # keep matching it for the store's lifetime.
        if canon.digest_bytes(role_tag, payload) != digest:
            raise StoreError(f"object tampered at rest: {digest}")
        return payload


def upload_bundle(store: LocalBundleStore, bundle_dir: str,
                  max_retries: int = 3, sleep=time.sleep) -> dict:
    """Upload a sealed evidence bundle into the store, retryably.

    Sealing happens FIRST (coh-ev-01); upload is a separate, retryable
    step. Each object is put independently: a crash or transient failure
    mid-upload leaves some objects stored — a retry re-verifies and skips
    those, so partial uploads are RESUMED, never duplicated or faked.
    Returns {uploaded, already_present, failed} plus the manifest digest.
    """
    bundle = Path(bundle_dir)
    manifest_path = bundle / "evidence-manifest.json"
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, json.JSONDecodeError) as e:
        raise StoreError(f"cannot read evidence manifest: {e}") from e

    uploaded, present, failed = [], [], []
    for obj in manifest.get("objects", []):
        rel, digest = obj.get("path"), obj.get("digest")
        if not isinstance(rel, str) or not isinstance(digest, str):
            failed.append({"path": rel, "reason": "malformed-manifest-entry"})
            continue
        fp = bundle / rel
        try:
            payload = fp.read_bytes()
        except OSError as e:
            failed.append({"path": rel, "reason": f"unreadable: {e}"})
            continue
        if canon.digest_bytes("evidence-manifest/v1", payload) != digest:
            failed.append({"path": rel, "reason": "tampered-since-seal"})
            continue
        # Already-held objects are verified skips (this is what makes a
        # retried upload safe and idempotent): the stored bytes must match
        # the sealed payload, or the store is tampered — a hard stop, never
        # a silent skip.
        if store_has(store, digest):
            try:
                existing = store.get(digest)
            except StoreError as e:
                if "tampered" in str(e) or "collision" in str(e):
                    raise  # tamper signal: never retried, never skipped past
                existing = None  # transient read failure: fall through to put
            if existing is not None:
                if existing != payload:
                    raise StoreError(
                        f"stored object differs from sealed payload: {digest}")
                present.append({"path": rel, "digest": digest})
                continue
        stored = False
        for attempt in range(max_retries):
            try:
                store.put("evidence-manifest/v1", payload)
                stored = True
                break
            except StoreError as e:
                if "collision" in str(e):
                    raise  # never retry a tamper signal
                if attempt < max_retries - 1:
                    sleep(backoff(attempt))
        if stored:
            uploaded.append({"path": rel, "digest": digest})
        else:
            failed.append({"path": rel, "reason": "store-unavailable"})

    # The manifest itself is the last object (an upload without its index
    # is only half an upload).
    manifest_digest = canon.digest_bytes("evidence-manifest/v1",
                                         manifest_bytes)
    if store_has(store, manifest_digest):
        present.append({"path": "evidence-manifest.json",
                        "digest": manifest_digest})
    else:
        for attempt in range(max_retries):
            try:
                store.put("evidence-manifest/v1", manifest_bytes)
                uploaded.append({"path": "evidence-manifest.json",
                                 "digest": manifest_digest})
                break
            except StoreError as e:
                if "collision" in str(e):
                    raise
                if attempt == max_retries - 1:
                    failed.append({"path": "evidence-manifest.json",
                                   "reason": "store-unavailable"})
                else:
                    sleep(backoff(attempt))

    return {"uploaded": uploaded, "already_present": present,
            "failed": failed, "manifest_digest": manifest_digest}


def store_has(store: LocalBundleStore, digest: str) -> bool:
    try:
        return store.has(digest)
    except StoreError:
        return False


# --- complete decision-cache key (coh-ctx-05) --------------------------------

def decision_cache_key(*, subject_digest, openspec_digest, policy_digest,
                       context_digest, evaluator_image_digest,
                       plugin_digests=None, captured_fact_digests=None,
                       ttl_seconds=None, retention_days=None,
                       signer_key_id=None) -> str:
    """The TOTAL cache key: every input a decision depends on.

    Omitting an input from the key is how stale decisions get replayed as
    fresh ones; this constructor is deliberately exhaustive (keyword-only,
    everything bound) so a caller cannot accidentally build a partial key.
    A None evaluator image is part of the key too — decisions made under
    unknown identity are not interchangeable with attributed ones.
    """
    parts = {
        "subject_digest": subject_digest,
        "openspec_digest": openspec_digest,
        "policy_digest": policy_digest,
        "context_digest": context_digest,
        "evaluator_image_digest": evaluator_image_digest,
        "plugin_digests": sorted(plugin_digests or []),
        "captured_fact_digests": sorted(captured_fact_digests or []),
        "ttl_seconds": ttl_seconds,
        "retention_days": retention_days,
        "signer_key_id": signer_key_id,
    }
    return canon.digest_obj("context/v1", {"cache-key/v1": parts})


def cache_entry_valid(entry, *, now_epoch: float, ttl_seconds,
                      retention_days) -> bool:
    """TTL + retention invalidation for a decision-cache entry (coh-ev-04).

    An entry is valid only when BOTH its TTL and its retention window are
    still open. A malformed entry (missing/epoch fields) is invalid — a
    cache that cannot prove freshness must miss, never hit.
    """
    if not isinstance(entry, dict):
        return False
    stored = entry.get("stored_epoch")
    if not isinstance(stored, (int, float)):
        return False
    if ttl_seconds is not None and now_epoch - stored > ttl_seconds:
        return False
    if retention_days is not None:
        if now_epoch - stored > retention_days * 86400:
            return False
    return True
