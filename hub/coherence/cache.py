# // spec: coh-ctx-05
"""Complete cache key (coh-ctx-05, design.md:251): a signed cached result is
reusable only when EVERY bound identity component matches exactly — subject,
package, policy, evaluation-context, evaluator image, plugin digests,
captured-fact digests — and only within a policy TTL while retention and
signer validity hold. The four-digest v1 subset is explicitly insufficient.

Two properties shape the implementation:

* The key is domain-separated and covers the full material object, so any
  component drift — including a re-captured fact set that leaves the context
  file byte-identical — moves the key. Stored records additionally carry the
  full `key_material` and lookup re-verifies it component-by-component: a
  collision, a renamed file, or a hand-edited record cannot borrow another
  identity's cached result.
* Time is never ambient. TTL is evaluated against the caller's `as_of` (the
  trusted `evaluation_time` of the requesting context), never the host clock
  (design.md:R2), and an undeclared TTL fails closed — reuse is granted by
  policy, not defaulted.

Validity of the two things the key cannot itself decide — is the signing key
still valid (coh-ev-05), is the retained input the result was computed from
still inside its window (coh-ev-04) — is consulted through caller-supplied
predicates so this module stays free of env and network access
(TestStaticDefaultDeny). An entry that *needs* a check and has no predicate
to run it is not reused; an unsigned, un-retained entry needs neither.

A miss is always a first-class answer with a reason: full evaluation runs.
"""
import base64
import json
from datetime import datetime, timedelta
from pathlib import Path

from . import canon

_COMPONENTS = ("subject_digest", "package_digest", "policy_digest",
               "context_digest", "evaluator_image_digest",
               "plugin_digests", "captured_fact_digests")
_LIST_COMPONENTS = {"plugin_digests", "captured_fact_digests"}
_ENTRY_DIR = "entries"


class CacheError(ValueError):
    """A complete key could not be formed (missing/invalid component)."""


def _now_ts(ts: str) -> datetime:
    # A non-string time (an int in a tampered/corrupt record, a caller bug) is
    # the same class of failure as an unparseable one — ValueError, never an
    # AttributeError escaping the documented miss contract.
    if not isinstance(ts, str):
        raise ValueError(f"time must be a string, got {type(ts).__name__}")
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _norm_list(val, name: str, allow_empty: bool) -> list:
    if not isinstance(val, list):
        raise CacheError(f"cache-component-not-a-list:{name}")
    if not allow_empty and not val:
        raise CacheError(f"cache-component-empty:{name}")
    for item in val:
        if not isinstance(item, str) or not item:
            raise CacheError(f"cache-component-item-invalid:{name}")
    return sorted(val)


def key(material: dict) -> str:
    """The cache key over the COMPLETE bound identity. Today plugin_digests
    is a validated empty set (launcher.py refuses plugins until an approved
    sandbox ADR exists); the component is in the key so that when plugins
    land, key completeness already covers them."""
    if not isinstance(material, dict):
        raise CacheError("cache-material-must-be-an-object")
    material = dict(material)
    for comp in _COMPONENTS:
        val = material.get(comp)
        if comp in _LIST_COMPONENTS:
            # An explicit empty list is a claim of "nothing bound"; a missing
            # or None value is an incomplete key. The two must not collapse.
            if val is None:
                raise CacheError(f"cache-component-missing:{comp}")
            material[comp] = _norm_list(val, comp, allow_empty=True)
        elif not isinstance(val, str) or not val:
            raise CacheError(f"cache-component-missing:{comp}")
    return canon.digest_obj("context/v1", {
        "kind": "cache-key/v1",
        **{c: material[c] for c in _COMPONENTS}})


def put(store_root, material: dict, payload: bytes, *, cached_at: str,
        signer: dict = None, retained_refs: list = None) -> str:
    """Record a sealed result under its complete key. `signer` (key_id +
    signer_set_digest) marks a promotion-authorizing signed entry;
    `retained_refs` records the retention bundle refs the evaluation consumed
    so reuse can later be checked against them. Returns the key."""
    k = key(material)
    if not isinstance(payload, (bytes, bytearray)):
        raise CacheError("cache-payload-must-be-bytes")
    try:
        _now_ts(cached_at)
    except (ValueError, TypeError):
        raise CacheError("cache-bad-time") from None
    if retained_refs is not None:
        _norm_list(retained_refs, "retained_refs", allow_empty=False)
    if signer is not None and not signer.get("signer_set_digest"):
        raise CacheError("cache-signer-record-incomplete")
    root = Path(store_root)
    (root / _ENTRY_DIR).mkdir(parents=True, exist_ok=True)
    record = {"api_version": "devgate.spec-coherence.cache/v1",
              "key": k, "key_material": {c: material[c] for c in _COMPONENTS},
              "cached_at": cached_at, "signer": signer,
              "retained_refs": retained_refs or [],
              "payload": base64.b64encode(bytes(payload)).decode("ascii")}
    (root / _ENTRY_DIR / f"{k}.json").write_text(json.dumps(record), encoding="utf-8")
    return k


def get(store_root, material: dict, *, as_of: str, ttl_seconds=None,
        signer_ok=None, retention_ok=None) -> dict:
    """Look up a cached result. Returns {"hit": True, "payload": bytes} or
    {"hit": False, "reason": <why>}; every failure mode is a miss with a
    reason — reuse requires the complete key, a declared TTL still in force,
    and (for entries needing them) passing validity predicates."""
    try:
        k = key(material)
    except CacheError as e:
        return {"hit": False, "reason": f"bad-material:{e}"}
    fp = Path(store_root) / _ENTRY_DIR / f"{k}.json"
    if not fp.is_file():
        return {"hit": False, "reason": "no-entry"}
    try:
        rec = json.loads(fp.read_text(encoding="utf-8"))
        payload = base64.b64decode(rec["payload"], validate=True)
    except (OSError, ValueError, KeyError, TypeError):
        # A corrupt/truncated/garbage record is a miss, never a traceback.
        return {"hit": False, "reason": "entry-unreadable"}
    stored = rec.get("key_material") or {}
    for comp in _COMPONENTS:
        if comp in _LIST_COMPONENTS:
            drift = sorted(stored.get(comp) or []) != sorted(material.get(comp) or [])
        else:
            drift = stored.get(comp) != material.get(comp)
        if drift:
            return {"hit": False, "reason": f"key-drift:{comp}"}

    # --- TTL: policy-declared, clock from as_of, never ambient.
    if not isinstance(ttl_seconds, int) or ttl_seconds < 0:
        return {"hit": False, "reason": "ttl-undeclared"}
    try:
        age = _now_ts(as_of) - _now_ts(rec["cached_at"])
    except (ValueError, TypeError, KeyError):
        return {"hit": False, "reason": "bad-time"}
    if age < timedelta(0):
        # Two trusted times that contradict each other are not trustworthy,
        # even though a negative age satisfies `age <= ttl` arithmetically.
        return {"hit": False, "reason": "bad-window"}
    if age > timedelta(seconds=ttl_seconds):
        return {"hit": False, "reason": "ttl-expired"}

    # --- Signer validity (coh-ev-05): a signed entry is only reusable while
    # its signer still checks out; no predicate means unchecked means unsafe.
    signer = rec.get("signer")
    if signer:
        if signer_ok is None:
            return {"hit": False, "reason": "signer-unchecked"}
        ok, reason = signer_ok(signer)
        if not ok:
            return {"hit": False, "reason": f"signer-invalid:{reason}"}

    # --- Retention validity (coh-ev-04): a result computed from retained
    # input bytes is reusable only while that retention window holds.
    refs = rec.get("retained_refs") or []
    if refs:
        if retention_ok is None:
            return {"hit": False, "reason": "retention-unchecked"}
        ok, reason = retention_ok({"retained_refs": refs})
        if not ok:
            return {"hit": False, "reason": f"retention-invalid:{reason}"}

    return {"hit": True, "payload": payload}
