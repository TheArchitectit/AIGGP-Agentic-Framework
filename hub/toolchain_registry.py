"""hub.toolchain_registry — the Registry seam for the toolchain capability.

// spec: mon-tc-02, mon-tc-03, mon-tc-04

`hub/registry.py` sits at DevGate's 500-line source hard limit, and the
toolchain capability needs several delegator methods on it. They live here as
a mixin so the line budget stays honest: the methods are still ON the Registry
(caller code, the schema guard and the tests all reach them through a Registry
instance) but their text is counted in a module of its own.

The split rule is the one `record_gap_report` already documents: the writing
half lives in `toolchain_creds` / `toolchain_store`, which are dict-only, and
the seam here adds only resolution by name, which is Registry's job. Methods
that need `find_runner` or `_now_iso` stayed in `registry.py` because they are
more Registry than delegation; everything below is pure forwarding over
`self._data`.
"""

from __future__ import annotations

from . import toolchain_creds


class ToolchainRegistryMixin:
    """Toolchain delegators mixed into `Registry` (mon-tc-02..04)."""

    # --- toolchain requests (mon-tc-02) -------------------------------------

    def toolchain_requests(self) -> list[dict]:
        """Every request row, open and settled (mon-tc-02).

        A registry written before this capability shipped has no such key, and
        reading it as an empty list is correct: an empty set means "nobody has
        asked for anything", which mon-tc-06 insists is not the same statement as
        "every lane is provisioned".
        """
        return self._data.setdefault("toolchain_requests", [])

    # --- toolchain credentials (mon-tc-03) -----------------------------------

    def toolchain_credentials(self) -> list[dict]:
        return self._data.setdefault("toolchain_credentials", [])

    def classify_credential(self, presented: str | None):
        return toolchain_creds.classify(self._data, presented)

    def add_toolchain_credential(self, **kw) -> None:
        toolchain_creds.add_credential(self._data, **kw)

    def consume_toolchain_nonce(self, nonce: str) -> None:
        toolchain_creds.consume_nonce(self._data, nonce)

    def is_toolchain_nonce_consumed(self, nonce: str) -> bool:
        return toolchain_creds.is_nonce_consumed(self._data, nonce)

    def decide_request(self, request_id: str, *, action: str,
                       credential_class: str | None, scope: str | None,
                       credential_id: str | None, actor: str | None,
                       principal: str | None, nonce: str | None,
                       expected_version: int | None, note: str | None,
                       now: str) -> dict:
        # mon-tc-03, mon-tc-04: the transitions engine is dict-only, so the
        # writing half lives in hub/toolchain_creds.py. The caller owns the
        # lock and the save.
        return toolchain_creds.decide_request(
            self._data, request_id, action=action,
            credential_class=credential_class, scope=scope,
            credential_id=credential_id, actor=actor, principal=principal,
            nonce=nonce, expected_version=expected_version, note=note, now=now)
