import time


class TokenBucket:
    """Token-bucket rate limiter."""

    def __init__(self, rate_per_sec, capacity):
        self.rate = rate_per_sec
        self.capacity = capacity
        self._tokens = float(capacity)
        self._updated = time.monotonic()

    def try_acquire(self, n=1):
        now = time.monotonic()
        self._tokens = min(self.capacity,
                           self._tokens + (now - self._updated) * self.rate)
        self._updated = now
        if self._tokens >= n:
            self._tokens -= n
            return True
        return False
