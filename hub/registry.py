"""hub.registry — runners.json load/save on the hub volume.

The registry is INSTANCE STATE: it lives on the hub's persistent volume on
monitor-hub and is never committed (mon-registry-01). Only the schema and a redacted
example ship in-repo under hub/schema/. Saves are atomic (tmp + os.replace)
so a crash mid-write cannot corrupt the fleet registry.

// spec: mon-registry-01
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import tempfile
from datetime import datetime, timezone

from . import tokens

SCHEMA_VERSION = 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class RegistryError(Exception):
    """Raised when the registry file is missing required structure."""


class Registry:
    """In-memory view of runners.json with atomic persistence.

    // spec: mon-enroll-01
    """

    def __init__(self, path: str, auto_init: bool = True) -> None:
        """auto_init=True (the hub's startup mode) creates a fresh registry
        when the file does not exist yet; a missing file with auto_init=False
        is a configuration error and raises."""
        self.path = path
        self._data: dict = {}
        if not os.path.exists(path) and auto_init:
            self._data = {"version": SCHEMA_VERSION,
                          "token_salt": secrets.token_hex(16),
                          "enrollment_tokens": [], "runners": []}
            return
        self.load()

    # --- persistence ------------------------------------------------------

    def load(self) -> None:
        with open(self.path, encoding="utf-8") as fh:
            self._data = json.load(fh)
        for key in ("version", "enrollment_tokens", "runners"):
            if key not in self._data:
                raise RegistryError(f"registry missing required key: {key}")
        # Per-registry salt for token hashing at rest (mon-sec-02). Generated
        # once and persisted; a volume read yields verifier hashes, not tokens.
        self._data.setdefault("token_salt", secrets.token_hex(16))
        # Migrate any legacy plaintext heartbeat tokens in memory: hash them
        # with the salt so existing enrollments keep working, and drop the
        # plaintext field. Persisted on the next save (the hub saves at
        # startup, so the upgrade lands immediately).
        for runner in self._data["runners"]:
            plain = runner.pop("heartbeat_token", None)
            if plain and not runner.get("heartbeat_token_hash"):
                runner["heartbeat_token_hash"] = self._hash_token(plain)

    # --- token hashing (mon-sec-02) -----------------------------------------

    def _hash_token(self, token: str) -> str:
        salt = self._data.get("token_salt") or ""
        return "sha256:" + hashlib.sha256(
            (salt + token).encode("utf-8")).hexdigest()

    def _token_matches(self, presented: str, stored_hash: str | None) -> bool:
        if not presented or not stored_hash:
            return False
        return hmac.compare_digest(self._hash_token(presented), stored_hash)

    def save(self) -> None:
        """Atomic write: tmp file in the same directory, then os.replace."""
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".runners-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2)
                fh.write("\n")
            os.replace(tmp_path, self.path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    # --- enrollment tokens (one-time) --------------------------------------

    def add_enrollment_token(self, token: str) -> None:
        if token not in self._data["enrollment_tokens"]:
            self._data["enrollment_tokens"].append(token)

    def consume_enrollment_token(self, presented: str) -> bool:
        """Verify AND consume a one-time enrollment token (mon-enroll-01)."""
        for candidate in list(self._data["enrollment_tokens"]):
            if tokens.verify(presented, candidate):
                self._data["enrollment_tokens"].remove(candidate)
                return True
        return False

    # --- runners ------------------------------------------------------------

    def find_runner(self, name: str) -> dict | None:
        for runner in self._data["runners"]:
            if runner.get("name") == name:
                return runner
        return None

    def enroll(self, runner_name: str, repo: str, labels: list[str],
               host_alias: str) -> tuple[dict, str]:
        """Record identity and mint the per-runner heartbeat token.

        Returns (runner_record, plaintext_token): the plaintext leaves the hub
        exactly ONCE, in the enroll response; only its salted hash is stored
        (mon-sec-02 — a registry read at rest yields no usable token)."""
        heartbeat_token = tokens.mint_token()
        runner = {
            "name": runner_name,
            "repo": repo,
            "labels": labels,
            "host_alias": host_alias,
            "enrolled_at": _now_iso(),
            "heartbeat_token_hash": self._hash_token(heartbeat_token),
            "last_heartbeat": None,
            "last_job_seen": None,
            "disk_ok": None,
            "podman_ok": None,
            "enrolled": True,
        }
        self._data["runners"].append(runner)
        return runner, heartbeat_token

    def heartbeat(self, runner_name: str, last_job_seen: str | None,
                  disk_ok: bool | None, podman_ok: bool | None) -> bool:
        """Update freshness + health fields for a verified runner."""
        runner = self.find_runner(runner_name)
        if runner is None or not runner.get("enrolled", False):
            return False
        runner["last_heartbeat"] = _now_iso()
        if last_job_seen is not None:
            runner["last_job_seen"] = last_job_seen
        if disk_ok is not None:
            runner["disk_ok"] = disk_ok
        if podman_ok is not None:
            runner["podman_ok"] = podman_ok
        return True

    def verify_heartbeat_token(self, runner_name: str, presented: str) -> bool:
        """True when the token matches an enrolled (non-revoked) runner.
        Compares salted hashes with a constant-time digest compare."""
        runner = self.find_runner(runner_name)
        if runner is None or not runner.get("enrolled", False):
            return False
        return self._token_matches(presented, runner.get("heartbeat_token_hash"))

    def revoke(self, runner_name: str) -> bool:
        """Mark a runner unenrolled; subsequent heartbeats must 401
        (mon-enroll-01). The stored verifier is cleared too (mon-sec-02)."""
        runner = self.find_runner(runner_name)
        if runner is None:
            return False
        runner["enrolled"] = False
        runner["heartbeat_token_hash"] = None
        return True

    def runners(self) -> list[dict]:
        return self._data["runners"]
