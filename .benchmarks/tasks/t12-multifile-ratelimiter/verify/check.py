import sys, time
repo = sys.argv[1]
sys.path.insert(0, repo)
from ratelimit import TokenBucket
from client import fetch_with_limit
bucket = TokenBucket(rate_per_sec=1000, capacity=2)
assert bucket.try_acquire() is True
assert bucket.try_acquire() is True
assert bucket.try_acquire() is False, "bucket should be empty"
time.sleep(0.05)  # refill at 1000/s -> ~50 tokens worth of time
assert bucket.try_acquire() is True, "bucket must refill over time"
body, reason = fetch_with_limit("http://x", bucket=bucket)
assert body == "content:http://x" and reason is None, (body, reason)
empty = TokenBucket(rate_per_sec=0.0001, capacity=0)
body, reason = fetch_with_limit("http://y", bucket=empty)
assert body is None and reason == "rate-limited", (body, reason)
print("hidden verification passed")
