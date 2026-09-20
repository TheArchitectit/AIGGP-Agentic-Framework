"""HTTP-ish client."""

from ratelimit import TokenBucket  # noqa: F401  (re-export for callers)


def fetch(url):
    """Pretend network fetch."""
    return f"content:{url}"


def fetch_with_limit(url, bucket=None):
    """Fetch unless the bucket is out of tokens."""
    if bucket is not None and not bucket.try_acquire():
        return None, "rate-limited"
    return fetch(url), None
