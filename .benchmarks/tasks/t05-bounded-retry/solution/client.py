import time


class ConnectionError(RuntimeError):
    pass


def fetch_with_retry(fetch, max_retries=3, sleep=time.sleep):
    """Call fetch(); on failure retry up to max_retries times."""
    attempts = max_retries + 1
    for i in range(attempts):
        try:
            return fetch()
        except ConnectionError:
            if i == attempts - 1:
                raise
            sleep(0.01)
