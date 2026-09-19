# // spec: coh-ctx-05
"""Complete cache key (coh-ctx-05, design.md:251): a signed cached result is
reusable ONLY when every bound identity matches exactly — subject, package,
policy, evaluation-context, evaluator image, plugin digests, captured-fact
digests — and only within a policy TTL and while retention and signer validity
hold. The v1 four-digest subset is explicitly insufficient.

Every temporal/validity check reads an explicit `as_of` from the caller's
trusted context, never the host clock (R2). The cache stores no network path
(TestStaticDefaultDeny still holds); a hit returns the exact bytes that were
put, and every miss reports a reason so a caller can see which gate fired.

All fixtures synthetic (R9).
"""
import base64
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import cache

FIXED = "2026-09-17T00:00:00Z"
PAYLOAD = b'{"decision":"PASS"}'
TTL = 3600  # seconds


def _material(**over):
    """A complete key material with every one of the seven components set to a
    distinct synthetic value; `over` replaces one at a time."""
    m = {
        "subject_digest": "sha256:" + "1" * 64,
        "package_digest": "sha256:" + "2" * 64,
        "policy_digest": "sha256:" + "3" * 64,
        "context_digest": "sha256:" + "4" * 64,
        "evaluator_image_digest": "sha256:" + "5" * 64,
        "plugin_digests": ["sha256:" + "6" * 64, "sha256:" + "7" * 64],
        "captured_fact_digests": ["sha256:" + "8" * 64, "sha256:" + "9" * 64],
    }
    m.update(over)
    return m


def _signer_ok(record):
    return True, "ok"


def _retention_ok(record):
    return True, "ok"


class TestFullKeyReuse(unittest.TestCase):
    def test_an_identical_complete_key_within_all_validity_hits(self):
        """The positive case that makes the misses meaningful: with every
        component matching, a TTL in force, and both validity gates green, the
        exact sealed bytes come back."""
        with tempfile.TemporaryDirectory() as td:
            m = _material()
            cache.put(td, m, PAYLOAD, cached_at=FIXED,
                      signer={"key_id": "k1",
                              "signer_set_digest": "sha256:" + "a" * 64})
            res = cache.get(td, m, as_of="2026-09-17T00:30:00Z", ttl_seconds=TTL,
                            signer_ok=_signer_ok)
            self.assertTrue(res["hit"], res.get("reason"))
            self.assertEqual(res["payload"], PAYLOAD)


class TestKeyCompleteness(unittest.TestCase):
    """coh-ctx-05's scenario 'partial key match' and its sentence 'the
    four-digest subset is not a sufficient cache key'. subject/package/policy/
    evaluator stay pinned while each of the other three components changes on
    its own — every one must force a MISS, proving the cache actually reads
    context, plugins and captured-facts, not just the four."""

    def test_a_result_bound_to_an_older_context_is_a_miss(self):
        with tempfile.TemporaryDirectory() as td:
            cache.put(td, _material(), PAYLOAD, cached_at=FIXED)
            res = cache.get(td, _material(context_digest="sha256:" + "z" * 64),
                            as_of=FIXED, ttl_seconds=TTL)
            self.assertFalse(res["hit"])
            self.assertIn("no-entry", res["reason"])

    def test_a_changed_captured_fact_set_is_a_miss(self):
        with tempfile.TemporaryDirectory() as td:
            cache.put(td, _material(), PAYLOAD, cached_at=FIXED)
            res = cache.get(td, _material(
                captured_fact_digests=["sha256:" + "8" * 64,
                                       "sha256:" + "e" * 64]),
                as_of=FIXED, ttl_seconds=TTL)
            self.assertFalse(res["hit"], "re-captured fact must not reuse the old result")

    def test_a_changed_plugin_set_is_a_miss(self):
        with tempfile.TemporaryDirectory() as td:
            cache.put(td, _material(), PAYLOAD, cached_at=FIXED)
            res = cache.get(td, _material(plugin_digests=["sha256:" + "6" * 64]),
                            as_of=FIXED, ttl_seconds=TTL)
            self.assertFalse(res["hit"], "a different plugin set is a different identity")

    def test_component_drift_sweeps_every_one_of_the_seven(self):
        """Sub-test sweep: mutate exactly one component at a time, each must
        miss; the unmutated baseline must hit. Each component is therefore
        independently load-bearing — no single one is masked by another."""
        with tempfile.TemporaryDirectory() as td:
            base = _material()
            cache.put(td, base, PAYLOAD, cached_at=FIXED)
            variants = {
                "subject": _material(subject_digest="sha256:" + "0" * 64),
                "package": _material(package_digest="sha256:" + "0" * 64),
                "policy": _material(policy_digest="sha256:" + "0" * 64),
                "context": _material(context_digest="sha256:" + "0" * 64),
                "evaluator": _material(evaluator_image_digest="sha256:" + "0" * 64),
                "plugins": _material(plugin_digests=["sha256:" + "0" * 64]),
                "facts": _material(captured_fact_digests=["sha256:" + "0" * 64]),
            }
            for name, mat in variants.items():
                with self.subTest(component=name):
                    self.assertFalse(cache.get(td, mat, as_of=FIXED,
                                               ttl_seconds=TTL)["hit"])
            self.assertTrue(cache.get(td, base, as_of=FIXED,
                                      ttl_seconds=TTL)["hit"])

    def test_the_four_digest_subset_alone_would_collide(self):
        """Name the insufficiency at the key level: two materials identical on
        the four v1 digests but differing only on context must NOT share a
        cache key. (If the key were built from the four alone they would.)"""
        four_only = _material()
        older = dict(four_only, context_digest="sha256:" + "9" * 64)
        self.assertNotEqual(cache.key(four_only), cache.key(older))

    def test_an_incomplete_material_is_rejected_at_key_time(self):
        """A missing or empty component cannot form a complete key: the
        insufficiency of the four-digest subset must be enforced at key
        construction, not left to luck at lookup."""
        with tempfile.TemporaryDirectory() as td:
            m = _material()
            del m["context_digest"]
            with self.assertRaises(cache.CacheError) as cm:
                cache.key(m)
            self.assertIn("cache-component-missing:context_digest", str(cm.exception))
            m2 = _material(captured_fact_digests=None)
            with self.assertRaises(cache.CacheError):
                cache.key(m2)

    def test_key_is_independent_of_fact_and_plugin_list_order(self):
        """Ordering of a set-valued component must not change identity —
        otherwise two runs with the same content miss each other."""
        a = _material(plugin_digests=["sha256:" + "7" * 64, "sha256:" + "6" * 64],
                      captured_fact_digests=["sha256:" + "9" * 64,
                                             "sha256:" + "8" * 64])
        self.assertEqual(cache.key(a), cache.key(_material()),
                         "sorted components must hash identically regardless of input order")


class TestTimeToLive(unittest.TestCase):
    """'only within policy TTL'. A policy that declares no TTL authorizes no
    reuse window, so the cache fails closed to a miss rather than defaulting to
    'forever' — reuse is a granted privilege, not a default."""

    def test_an_undeclared_ttl_fails_closed_to_a_miss(self):
        with tempfile.TemporaryDirectory() as td:
            m = _material()
            cache.put(td, m, PAYLOAD, cached_at=FIXED)
            res = cache.get(td, m, as_of=FIXED, ttl_seconds=None)
            self.assertFalse(res["hit"])
            self.assertIn("ttl-undeclared", res["reason"])

    def test_a_result_past_its_ttl_is_a_miss(self):
        with tempfile.TemporaryDirectory() as td:
            m = _material()
            cache.put(td, m, PAYLOAD, cached_at=FIXED)
            past = (datetime.fromisoformat(FIXED.replace("Z", "+00:00"))
                    + timedelta(seconds=TTL + 1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            res = cache.get(td, m, as_of=past, ttl_seconds=TTL)
            self.assertFalse(res["hit"])
            self.assertIn("ttl-expired", res["reason"])

    def test_a_result_at_the_ttl_boundary_is_still_valid(self):
        with tempfile.TemporaryDirectory() as td:
            m = _material()
            cache.put(td, m, PAYLOAD, cached_at=FIXED)
            at = (datetime.fromisoformat(FIXED.replace("Z", "+00:00"))
                  + timedelta(seconds=TTL)).strftime("%Y-%m-%dT%H:%M:%SZ")
            res = cache.get(td, m, as_of=at, ttl_seconds=TTL)
            self.assertTrue(res["hit"], "the boundary instant is inside the window")

    def test_expiry_is_evaluated_against_as_of_not_the_host_clock(self):
        """If the check used datetime.now() this would be a time bomb and would
        violate design.md:R2. `as_of` is one second past FIXED, TTL is an hour:
        it must hit no matter what wall-clock the test runs under."""
        with tempfile.TemporaryDirectory() as td:
            m = _material()
            cache.put(td, m, PAYLOAD, cached_at=FIXED)
            res = cache.get(td, m, as_of="2026-09-17T00:00:01Z", ttl_seconds=TTL)
            self.assertTrue(res["hit"])

    def test_a_malformed_as_of_is_a_miss_not_a_default_hit(self):
        """An unparseable trusted time cannot silently pass the TTL gate."""
        with tempfile.TemporaryDirectory() as td:
            m = _material()
            cache.put(td, m, PAYLOAD, cached_at=FIXED)
            res = cache.get(td, m, as_of="not-a-time", ttl_seconds=TTL)
            self.assertFalse(res["hit"])
            self.assertIn("bad-time", res["reason"])

    def test_an_entry_dated_after_the_lookup_time_is_a_miss(self):
        """A negative age satisfies `age <= ttl` literally, but two trusted
        times in mutually contradictory order mean the inputs are not to be
        trusted — the same fail-closed doctrine as retention's bad-time. It
        must be a miss with a reason, never a silent 'within TTL'."""
        with tempfile.TemporaryDirectory() as td:
            m = _material()
            cache.put(td, m, PAYLOAD, cached_at=FIXED)
            res = cache.get(td, m, as_of="2026-09-16T00:00:00Z", ttl_seconds=TTL)
            self.assertFalse(res["hit"])
            self.assertIn("bad-window", res["reason"])

    def test_a_record_with_a_non_string_cached_at_is_a_miss_not_a_crash(self):
        """The entries directory is persisted JSON: a record whose cached_at
        is an int (corruption, a hand-edit) must fall to the documented miss
        contract, not escape AttributeError from the parser."""
        with tempfile.TemporaryDirectory() as td:
            m = _material()
            cache.put(td, m, PAYLOAD, cached_at=FIXED)
            entry = Path(td) / "entries" / (cache.key(m) + ".json")
            rec = json.loads(entry.read_text())
            rec["cached_at"] = 12345
            entry.write_text(json.dumps(rec))
            res = cache.get(td, m, as_of=FIXED, ttl_seconds=TTL)
            self.assertFalse(res["hit"])
            self.assertIn("bad-time", res["reason"])

    def test_a_non_string_as_of_is_a_miss_not_a_crash(self):
        with tempfile.TemporaryDirectory() as td:
            m = _material()
            cache.put(td, m, PAYLOAD, cached_at=FIXED)
            res = cache.get(td, m, as_of=999, ttl_seconds=TTL)
            self.assertFalse(res["hit"])
            self.assertIn("bad-time", res["reason"])

    def test_zero_ttl_reuses_only_the_instant_it_was_cached(self):
        """ttl_seconds=0 is the coherent degenerate policy (like 0-day
        retention): valid at the caching instant, expired one second later."""
        with tempfile.TemporaryDirectory() as td:
            m = _material()
            cache.put(td, m, PAYLOAD, cached_at=FIXED)
            self.assertTrue(cache.get(td, m, as_of=FIXED,
                                      ttl_seconds=0)["hit"])
            res = cache.get(td, m, as_of="2026-09-17T00:00:01Z", ttl_seconds=0)
            self.assertFalse(res["hit"])
            self.assertIn("ttl-expired", res["reason"])


class TestSignerValidity(unittest.TestCase):
    """'while signer validity holds' — and coh-ev-05's revoked-signer
    failure-injection case. The cached result was signed under a signer set
    (the context's signer_set_digest, which issue.py records and this finally
    consumes); a result is reusable only if a caller can attest that signer is
    still valid. With no validator wired, a signed entry is not reused."""

    def test_a_revoked_signer_makes_an_otherwise_matching_entry_a_miss(self):
        with tempfile.TemporaryDirectory() as td:
            m = _material()
            cache.put(td, m, PAYLOAD, cached_at=FIXED,
                      signer={"key_id": "k1",
                              "signer_set_digest": "sha256:" + "a" * 64})

            def revoked(record):
                return False, "signer-revoked"

            res = cache.get(td, m, as_of=FIXED, ttl_seconds=TTL, signer_ok=revoked)
            self.assertFalse(res["hit"])
            self.assertIn("signer-revoked", res["reason"])

    def test_a_signed_entry_without_a_signer_validator_is_not_reused(self):
        """Fail-closed: if we cannot check the signer's current validity, a
        signed cached result must not be trusted for reuse."""
        with tempfile.TemporaryDirectory() as td:
            m = _material()
            cache.put(td, m, PAYLOAD, cached_at=FIXED,
                      signer={"key_id": "k1",
                              "signer_set_digest": "sha256:" + "a" * 64})
            res = cache.get(td, m, as_of=FIXED, ttl_seconds=TTL, signer_ok=None)
            self.assertFalse(res["hit"])
            self.assertIn("signer-unchecked", res["reason"])

    def test_an_unsigned_entry_needs_no_signer_validator(self):
        """Stage 0/1 and replay results are unsigned and non-promotion-
        authorizing; the cache returns them without demanding a signer check —
        whether a returned result *authorizes promotion* is attest's call, not
        the cache's, so the gates stay orthogonal."""
        with tempfile.TemporaryDirectory() as td:
            m = _material()
            cache.put(td, m, PAYLOAD, cached_at=FIXED)  # no signer
            res = cache.get(td, m, as_of=FIXED, ttl_seconds=TTL, signer_ok=None)
            self.assertTrue(res["hit"])


class TestRetentionValidity(unittest.TestCase):
    """'while retention holds' — coh-ev-04: retention expiry invalidates cached-
    result reuse for the affected identities. An entry that depended on retained
    input bytes is reusable only while that retention is valid; the entry
    carries the refs so the caller can consult the retention channel."""

    def test_lapsed_input_retention_makes_a_matching_entry_a_miss(self):
        with tempfile.TemporaryDirectory() as td:
            m = _material()
            cache.put(td, m, PAYLOAD, cached_at=FIXED,
                      retained_refs=["sha256:" + "b" * 64])

            def expired(record):
                return False, "retention-expired"

            res = cache.get(td, m, as_of=FIXED, ttl_seconds=TTL,
                            retention_ok=expired)
            self.assertFalse(res["hit"])
            self.assertIn("retention-expired", res["reason"])

    def test_an_entry_with_retained_refs_and_no_validator_is_not_reused(self):
        with tempfile.TemporaryDirectory() as td:
            m = _material()
            cache.put(td, m, PAYLOAD, cached_at=FIXED,
                      retained_refs=["sha256:" + "b" * 64])
            res = cache.get(td, m, as_of=FIXED, ttl_seconds=TTL,
                            retention_ok=None)
            self.assertFalse(res["hit"])
            self.assertIn("retention-unchecked", res["reason"])

    def test_the_refs_an_entry_depended_on_are_carried_to_the_validator(self):
        """The retention predicate must see exactly the refs the entry
        recorded, or it cannot decide validity against the right bundles."""
        seen = {}

        def record_refs(record):
            seen.update(record)
            return True, "ok"

        with tempfile.TemporaryDirectory() as td:
            m = _material()
            refs = ["sha256:" + "b" * 64, "sha256:" + "c" * 64]
            cache.put(td, m, PAYLOAD, cached_at=FIXED, retained_refs=refs)
            cache.get(td, m, as_of=FIXED, ttl_seconds=TTL,
                      retention_ok=record_refs)
            self.assertEqual(sorted(seen["retained_refs"]), sorted(refs))


class TestStoreHygiene(unittest.TestCase):
    def test_a_garbage_entry_never_hits(self):
        """A corrupt or truncated record must fail closed to a miss, not
        surface a traceback or — worse — return garbage as a cached result."""
        with tempfile.TemporaryDirectory() as td:
            m = _material()
            cache.put(td, m, PAYLOAD, cached_at=FIXED)
            entry = Path(td) / "entries" / (cache.key(m) + ".json")
            entry.write_text("{ this is not json")
            res = cache.get(td, m, as_of=FIXED, ttl_seconds=TTL)
            self.assertFalse(res["hit"])
            self.assertIn("unreadable", res["reason"])

    def test_put_is_idempotent_and_stores_the_exact_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            m = _material()
            cache.put(td, m, PAYLOAD, cached_at=FIXED)
            cache.put(td, m, b"second-write", cached_at=FIXED)
            res = cache.get(td, m, as_of=FIXED, ttl_seconds=TTL)
            self.assertTrue(res["hit"])
            self.assertEqual(res["payload"], b"second-write")
            self.assertEqual(len(list((Path(td) / "entries").glob("*.json"))), 1)

    def test_a_keyed_entry_that_declares_a_different_material_is_a_miss(self):
        """Defense in depth: a hand-placed or renamed record whose stored
        key_material disagrees with its file name must not be reused — the
        component-by-component comparison catches a collision the hash alone
        would not."""
        with tempfile.TemporaryDirectory() as td:
            m = _material()
            cache.put(td, m, PAYLOAD, cached_at=FIXED)
            # Rewrite the record's stored material to claim a different subject.
            entry = Path(td) / "entries" / (cache.key(m) + ".json")
            rec = json.loads(entry.read_text())
            rec["key_material"]["subject_digest"] = "sha256:" + "0" * 64
            rec["payload"] = base64.b64encode(PAYLOAD).decode()
            entry.write_text(json.dumps(rec))
            res = cache.get(td, m, as_of=FIXED, ttl_seconds=TTL)
            self.assertFalse(res["hit"])
            self.assertIn("key-drift", res["reason"])


if __name__ == "__main__":
    unittest.main()
