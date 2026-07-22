"""Fixed per-domain delay between requests.

Simple sleep-based limiter for now; a token-bucket or backoff-aware version can
replace this later without changing crawl_one()'s call site.

State (`_last_request_at`) lives in process memory, so it's only enforced
within a single worker process. With multiple worker *containers* crawling
the same domain, each keeps its own independent clock, so the aggregate
request rate to that domain scales roughly linearly with worker count instead
of staying fixed -- a known, documented limitation, not silently ignored. See
tasks.py's module docstring and DECISIONS.md's Day 2 scaling entry for the
full tradeoff and why a Redis-backed shared limiter was deferred.
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
