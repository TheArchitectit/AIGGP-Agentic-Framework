"""hub.alerts_backoff — exponential backoff helper (P2 deferred).

Used by the notifier so a transient 429/503 on GitHub issue filing or
commenting does not silently drop the alert: the wrapper retries with
exponential backoff and re-raises only after the final attempt, so the
caller's existing error handling (log + return None/False) is unchanged.
"""
from __future__ import annotations

import urllib.error
import time


def with_backoff(func, *args, max_attempts: int = 3,
                 base_sec: float = 5.0, cap_sec: float = 60.0):
    """Retry func(*args) on transient HTTPError with exponential backoff.

    Re-raises the last HTTPError when all attempts are exhausted. Returns
    the function's return value on success.
    """
    last_exc: urllib.error.HTTPError | None = None
    for attempt in range(max_attempts):
        try:
            return func(*args)
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                time.sleep(min(base_sec * (2 ** attempt), cap_sec))
    assert last_exc is not None
    raise last_exc