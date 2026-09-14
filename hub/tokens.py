"""hub.tokens — enrollment + heartbeat token mint/verify/revoke.

Enrollment tokens are one-time (consumed on successful /enroll); heartbeat
tokens are per-runner and revocable. Verification is constant-time so a
network observer cannot timing-probe a valid token (mon-enroll-01: the hub
rejects unknown or revoked tokens).

// spec: mon-enroll-01
"""

from __future__ import annotations

import hmac
import secrets


def mint_token() -> str:
    """A fresh URL-safe 256-bit token. Callers store it; it is never logged."""
    return secrets.token_urlsafe(32)


def verify(presented: str, expected: str | None) -> bool:
    """Constant-time comparison; an absent expected token always fails."""
    if not presented or expected is None:
        return False
    return hmac.compare_digest(presented.encode(), expected.encode())
