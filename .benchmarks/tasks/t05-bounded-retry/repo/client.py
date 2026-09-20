import time


class ConnectionError(RuntimeError):
    pass


def fetch_with_retry(fetch, max_retries=3, sleep=time.sleep):
    """Call fetch(); on failure retry up to max_retries times."""
    while True:  # BUG: unbounded
        try:
            return fetch()
        except ConnectionError:
            sleep(0.01)
            continue
