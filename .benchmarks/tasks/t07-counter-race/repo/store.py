import time


class CounterStore:
    """Aggregates counters for the ingest pipeline.

    The read-modify-write below spans a slow lookup (simulated by the sleep,
    as with a remote-backed counter) — BUG: nothing holds a lock across it,
    so concurrent increments interleave and updates are lost.
    """

    def __init__(self):
        self._counts = {}

    def increment(self, key, by=1):
        current = self._counts.get(key, 0)   # read
        time.sleep(0.001)                    # slow middle (remote lookup)
        self._counts[key] = current + by     # write
        return current + by

    def get(self, key):
        return self._counts.get(key, 0)
