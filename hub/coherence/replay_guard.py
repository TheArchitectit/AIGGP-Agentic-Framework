# // spec: coh-oap-hard-06
"""Durable, atomic replay and idempotency guard for effect-bearing submissions.

Gate 2.5 (openspec/changes/harden-oap-evidence-verification): every
effect-bearing receiver MUST atomically enforce scoped nonce/request/
evaluation and idempotency uniqueness over trusted tenant, direction,
audience, operation, subject, and payload. Altered retries, duplicates,
expired submissions, and stale or unavailable replay state are
non-authorizing.

A submission is scoped to the exact tuple

    (producer_id, tenant, direction, audience, operation, subject,
     payload_digest)

plus its idempotency key. `submit` returns one of:

  admitted                    first sighting; the effect may proceed to the
                              next gate (admission is still NOT authorization)
  duplicate                   exact retry (same scope, same or newer
                              revocation snapshot); the receiver may only
                              hand back the previously recorded outcome
  conflict                    same idempotency key, different scope (altered
                              payload or another evaluation) -> deny
  expired                     the recorded claim is past its TTL; retries are
                              permanently non-authorizing, never re-admitted
  stale-revocation-snapshot   the presented revocation version is older than
                              the recorded one -> deny

Two backends: `InMemoryReplayBackend` for tests, `SQLiteReplayBackend` for
production durability across restart and concurrent claims.

GATE 0 QUARANTINE still applies: admission from this guard is NON-AUTHORIZING
and MUST NOT satisfy a mandatory, promotion, release, or OAP-effect check
until Gates 1-3 pass and the security reviewer plus OAP owner approve.
"""
import sqlite3
import threading
import time
from dataclasses import dataclass

NON_AUTHORIZING = True

ADMITTED = "admitted"
DUPLICATE = "duplicate"
CONFLICT = "conflict"
EXPIRED = "expired"
STALE_REVOCATION_SNAPSHOT = "stale-revocation-snapshot"

# Every non-`admitted` status denies a new side effect.
DENYING = frozenset({DUPLICATE, CONFLICT, EXPIRED, STALE_REVOCATION_SNAPSHOT})

SCOPE_FIELDS = (
    "producer_id", "tenant", "direction", "audience", "operation", "subject",
    "payload_digest",
)


@dataclass(frozen=True)
class ReplayScope:
    producer_id: str
    tenant: str
    direction: str
    audience: str
    operation: str
    subject: str
    payload_digest: str

    def scope_key(self) -> str:
        return "\x00".join(getattr(self, field) for field in SCOPE_FIELDS)


@dataclass(frozen=True)
class ReplayRecord:
    idempotency_key: str
    scope_key: str
    revocation_version: int
    created_at: float
    expires_at: float
    outcome: str


class InMemoryReplayBackend:
    """Test backend: atomic under concurrency via a process-wide lock."""

    def __init__(self):
        self._lock = threading.RLock()
        self._by_key = {}
        self._by_scope = {}

    def claim(self, idempotency_key, scope, revocation_version, now, ttl):
        with self._lock:
            existing = self._by_key.get(idempotency_key)
            if existing is None:
                existing = self._by_scope.get(scope.scope_key())
            if existing is not None:
                if revocation_version is not None and \
                        revocation_version < existing.revocation_version:
                    return STALE_REVOCATION_SNAPSHOT, existing.outcome
                if now >= existing.expires_at:
                    return EXPIRED, existing.outcome
                if existing.scope_key != scope.scope_key():
                    return CONFLICT, existing.outcome
                return DUPLICATE, existing.outcome
            record = ReplayRecord(
                idempotency_key=idempotency_key,
                scope_key=scope.scope_key(),
                revocation_version=revocation_version
                if revocation_version is not None else -1,
                created_at=now, expires_at=now + ttl, outcome=None)
            self._by_key[idempotency_key] = record
            self._by_scope[scope.scope_key()] = record
            return ADMITTED, None

    def record_outcome(self, idempotency_key, outcome):
        with self._lock:
            record = self._by_key.get(idempotency_key)
            if record is None or record.outcome is not None:
                return False
            self._by_key[idempotency_key] = ReplayRecord(
                idempotency_key=record.idempotency_key,
                scope_key=record.scope_key,
                revocation_version=record.revocation_version,
                created_at=record.created_at, expires_at=record.expires_at,
                outcome=outcome)
            return True

    def outcome(self, idempotency_key):
        with self._lock:
            record = self._by_key.get(idempotency_key)
            return record.outcome if record else None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS replay_claims (
    idempotency_key TEXT PRIMARY KEY,
    scope_key       TEXT NOT NULL UNIQUE,
    revocation_version INTEGER NOT NULL,
    created_at      REAL NOT NULL,
    expires_at      REAL NOT NULL,
    outcome         TEXT
)
"""


class SQLiteReplayBackend:
    """Production backend: durable across restart, atomic under concurrency."""

    def __init__(self, path):
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False,
                                     isolation_level=None)
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=FULL")
            self._conn.execute(_SCHEMA)

    def claim(self, idempotency_key, scope, revocation_version, now, ttl):
        scope_key = scope.scope_key()
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT scope_key, revocation_version, expires_at, outcome"
                    " FROM replay_claims WHERE idempotency_key = ?",
                    (idempotency_key,)).fetchone()
                if row is None:
                    row = self._conn.execute(
                        "SELECT scope_key, revocation_version, expires_at,"
                        " outcome FROM replay_claims WHERE scope_key = ?",
                        (scope_key,)).fetchone()
                if row is not None:
                    recorded_scope, recorded_version, expires_at, outcome = row
                    if revocation_version is not None and \
                            revocation_version < recorded_version:
                        status = STALE_REVOCATION_SNAPSHOT
                    elif now >= expires_at:
                        status = EXPIRED
                    elif recorded_scope != scope_key:
                        status = CONFLICT
                    else:
                        status = DUPLICATE
                    self._conn.execute("ROLLBACK")
                    return status, outcome
                self._conn.execute(
                    "INSERT INTO replay_claims (idempotency_key, scope_key,"
                    " revocation_version, created_at, expires_at, outcome)"
                    " VALUES (?, ?, ?, ?, ?, NULL)",
                    (idempotency_key, scope_key,
                     revocation_version if revocation_version is not None
                     else -1,
                     now, now + ttl))
                self._conn.execute("COMMIT")
                return ADMITTED, None
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def record_outcome(self, idempotency_key, outcome):
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE replay_claims SET outcome = ?"
                " WHERE idempotency_key = ? AND outcome IS NULL",
                (outcome, idempotency_key))
            return cursor.rowcount > 0

    def outcome(self, idempotency_key):
        row = self._conn.execute(
            "SELECT outcome FROM replay_claims WHERE idempotency_key = ?",
            (idempotency_key,)).fetchone()
        return row[0] if row else None

    def close(self):
        with self._lock:
            self._conn.close()


class ReplayGuard:
    """Atomic admission of effect-bearing submissions, scoped and idempotent."""

    def __init__(self, backend, *, ttl_seconds=300.0):
        self._backend = backend
        self._ttl = float(ttl_seconds)

    def submit(self, scope, *, idempotency_key, revocation_version=None,
               now=None):
        """Claim admission for one submission. Returns (status, prior_outcome).

        Only `admitted` begins a new effect; every other status denies, and
        `duplicate` carries the previously recorded (non-authorizing)
        outcome. A caller-supplied `now` keeps tests deterministic.
        """
        if not isinstance(scope, ReplayScope):
            raise TypeError("scope must be a ReplayScope")
        if now is None:
            now = time.time()
        return self._backend.claim(idempotency_key, scope,
                                   revocation_version, now, self._ttl)

    def record_outcome(self, idempotency_key, outcome):
        """Persist the submission's outcome; an exact retry may retrieve it."""
        return self._backend.record_outcome(idempotency_key, outcome)

    def outcome(self, idempotency_key):
        return self._backend.outcome(idempotency_key)


__all__ = [
    "ADMITTED", "CONFLICT", "DENYING", "DUPLICATE", "EXPIRED",
    "NON_AUTHORIZING", "STALE_REVOCATION_SNAPSHOT", "InMemoryReplayBackend",
    "ReplayGuard", "ReplayRecord", "ReplayScope", "SCOPE_FIELDS",
    "SQLiteReplayBackend",
]
