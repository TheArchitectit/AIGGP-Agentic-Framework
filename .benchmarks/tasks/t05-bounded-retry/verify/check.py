import sys, os
sys.path.insert(0, sys.argv[1])
import client

attempts = []
def always_fails():
    attempts.append(1)
    raise client.ConnectionError("down")
sleeps = []
try:
    client.fetch_with_retry(always_fails, max_retries=3, sleep=sleeps.append)
except client.ConnectionError:
    pass
else:
    raise AssertionError("should have raised after final failure")
assert len(attempts) == 4, f"expected exactly 4 attempts, got {len(attempts)}"
assert len(sleeps) == 3, f"expected 3 sleeps, got {len(sleeps)}"

attempts.clear(); sleeps.clear()
client.fetch_with_retry(lambda: "ok", max_retries=3, sleep=sleeps.append)
assert attempts == [] and sleeps == []
print("hidden verification passed")
