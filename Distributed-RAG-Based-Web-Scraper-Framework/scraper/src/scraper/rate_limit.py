"""Fixed per-domain delay between requests.

Simple sleep-based limiter for now; a token-bucket or backoff-aware version can
replace this later without changing crawl_one()'s call site.
"""

import os
import time
from urllib.parse import urlparse

DEFAULT_DELAY_SECONDS = 1.5


class RateLimiter:
    def __init__(self, delay_seconds: float | None = None) -> None:
        if delay_seconds is None:
            delay_seconds = float(os.environ.get("REQUEST_DELAY_SECONDS", DEFAULT_DELAY_SECONDS))
        self.delay_seconds = delay_seconds
        self._last_request_at: dict[str, float] = {}

    def wait(self, url: str) -> None:
        domain = urlparse(url).netloc
        last = self._last_request_at.get(domain)
        if last is not None:
            remaining = self.delay_seconds - (time.monotonic() - last)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at[domain] = time.monotonic()
