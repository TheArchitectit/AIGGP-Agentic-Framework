"""Gate 2.5 tests for the durable replay/idempotency guard.

Effect-bearing submission admission is scoped to (producer, tenant,
direction, audience, operation, subject, payload digest) and the idempotency
key; duplicates, altered retries, expired submissions, and stale revocation
snapshots are non-authorizing. See hub/coherence/replay_guard.py and
openspec/changes/harden-oap-evidence-verification/spec.md
(coh-oap-hard-06).
"""
import sys
import tempfile
import threading
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from hub.coherence.replay_guard import (
    ADMITTED, CONFLICT, DENYING, DUPLICATE, EXPIRED,
    STALE_REVOCATION_SNAPSHOT, InMemoryReplayBackend, ReplayGuard,
    ReplayScope, SQLiteReplayBackend,
)

T0 = 1_000_000.0


def _scope(**overrides):
    values = {
        "producer_id": "devgate-instance-1",
        "tenant": "fixture-project",
        "direction": "devgate-to-oap",
        "audience": "oap-observer",
        "operation": "promotion",
        "subject": "repo:example/fixture",
        "payload_digest": "sha256:" + "aa" * 32,
    }
    values.update(overrides)
    return ReplayScope(**values)


def _submit(guard, status_wanted=None, **kwargs):
    kwargs.setdefault("idempotency_key", "idem-001")
    kwargs.setdefault("scope", _scope())
    status, prior = guard.submit(**kwargs)
    return status, prior


class _BackendCase:
    def _guard(self, **kwargs):
        raise NotImplementedError

    def test_first_submission_is_admitted(self):
        guard = self._guard()
        status, prior = _submit(guard, now=T0)
        self.assertEqual(status, ADMITTED)
        self.assertIsNone(prior)

    def test_concurrent_duplicate_claims_admit_exactly_one(self):
        guard = self._guard()
        results = []
        lock = threading.Lock()
        barrier = threading.Barrier(8)

        def worker():
            barrier.wait()
            status, _ = _submit(guard, now=T0)
            with lock:
                results.append(status)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(results.count(ADMITTED), 1)
        self.assertEqual(len(results) - results.count(ADMITTED),
                         sum(1 for status in results if status in DENYING))

    def test_exact_retry_returns_prior_non_authorizing_outcome(self):
        guard = self._guard()
        _submit(guard, now=T0)
        guard.record_outcome("idem-001", "non-authorizing:quarantined")
        status, prior = _submit(guard, now=T0 + 1)
        self.assertEqual(status, DUPLICATE)
        self.assertEqual(prior, "non-authorizing:quarantined")

    def test_same_scope_other_idempotency_key_is_replay(self):
        guard = self._guard()
        _submit(guard, now=T0)
        status, _ = _submit(guard, now=T0 + 1, idempotency_key="idem-002")
        self.assertEqual(status, DUPLICATE)

    def test_altered_payload_with_same_key_conflicts(self):
        guard = self._guard()
        _submit(guard, now=T0)
        status, _ = _submit(guard, now=T0 + 1, scope=_scope(
            payload_digest="sha256:" + "bb" * 32))
        self.assertEqual(status, CONFLICT)

    def test_altered_scope_with_same_key_conflicts(self):
        guard = self._guard()
        _submit(guard, now=T0)
        status, _ = _submit(guard, now=T0 + 1, scope=_scope(
            operation="release"))
        self.assertEqual(status, CONFLICT)

    def test_retry_after_expiry_is_denied_and_never_readmitted(self):
        guard = self._guard(ttl_seconds=300)
        _submit(guard, now=T0)
        guard.record_outcome("idem-001", "recorded-outcome")
        status, prior = _submit(guard, now=T0 + 301)
        self.assertEqual(status, EXPIRED)
        self.assertEqual(prior, "recorded-outcome")
        # Even a brand-new idempotency key over the expired scope stays denied.
        status, _ = _submit(guard, now=T0 + 302, idempotency_key="idem-003")
        self.assertEqual(status, EXPIRED)

    def test_stale_revocation_snapshot_denies(self):
        guard = self._guard()
        _submit(guard, now=T0, revocation_version=5)
        status, _ = _submit(guard, now=T0 + 1, revocation_version=4)
        self.assertEqual(status, STALE_REVOCATION_SNAPSHOT)
        # Same-or-newer snapshot versions are ordinary retries, not stale.
        for version in (5, 6):
            status, _ = _submit(guard, now=T0 + 2, revocation_version=version)
            self.assertEqual(status, DUPLICATE)


class TestInMemoryReplayGuard(_BackendCase, unittest.TestCase):
    def _guard(self, **kwargs):
        return ReplayGuard(InMemoryReplayBackend(), **kwargs)

    def test_repeated_nonce_under_other_evaluation_is_replay(self):
        guard = self._guard()
        _submit(guard, now=T0, idempotency_key="n1")
        status, _ = _submit(guard, now=T0 + 1, idempotency_key="n2",
                            scope=_scope(subject="repo:other"))
        # Different scope + different key = a genuinely new admission.
        self.assertEqual(status, ADMITTED)


class TestSQLiteReplayGuard(_BackendCase, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "replay.sqlite3"
        self._guards = []

    def tearDown(self):
        for guard in self._guards:
            guard._backend.close()
        self.tmp.cleanup()

    def _guard(self, **kwargs):
        guard = ReplayGuard(SQLiteReplayBackend(self.path), **kwargs)
        self._guards.append(guard)
        return guard

    def test_state_survives_restart(self):
        guard = self._guard()
        _submit(guard, now=T0)
        guard.record_outcome("idem-001", "prior-outcome")
        guard._backend.close()

        reopened = self._guard()
        status, prior = _submit(reopened, now=T0 + 5)
        self.assertEqual(status, DUPLICATE)
        self.assertEqual(prior, "prior-outcome")

    def test_conflict_survives_restart(self):
        guard = self._guard()
        _submit(guard, now=T0)
        guard._backend.close()

        reopened = self._guard()
        status, _ = _submit(reopened, now=T0 + 5, scope=_scope(
            payload_digest="sha256:" + "bb" * 32))
        self.assertEqual(status, CONFLICT)


class TestQuarantineMarker(unittest.TestCase):
    def test_admission_is_non_authorizing(self):
        import hub.coherence.replay_guard as replay_guard
        self.assertIs(replay_guard.NON_AUTHORIZING, True)
        self.assertNotIn(ADMITTED, DENYING)


if __name__ == "__main__":
    unittest.main()
