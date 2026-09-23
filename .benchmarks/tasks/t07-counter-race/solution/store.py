import threading
import time


class CounterStore:
    """Aggregates counters for the ingest pipeline (thread-safe)."""

    def __init__(self):
        self._counts = {}
        self._lock = threading.Lock()

    def increment(self, key, by=1):
        with self._lock:
            current = self._counts.get(key, 0)   # read
            time.sleep(0.001)                    # slow middle (remote lookup)
            self._counts[key] = current + by     # write
            return current + by

    def get(self, key):
        with self._lock:
            return self._counts.get(key, 0)
