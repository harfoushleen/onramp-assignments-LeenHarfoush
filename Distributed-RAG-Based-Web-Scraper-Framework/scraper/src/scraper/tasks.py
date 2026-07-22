"""Celery tasks: thin wrappers around crawl_one() that let a queued job
trigger the same fetch -> parse -> store pipeline the demo scripts call
directly.

robots_checker and rate_limiter are created once at module import time (i.e.
once per worker process) rather than per task, so their per-domain caches
(robots.txt rules, last-request timestamps) actually persist across the many
tasks a single worker processes -- a fresh RateLimiter per task would never
remember the previous request and the delay would do nothing. This is
process-local: with more than one worker process, each has its own cache and
rate limiting is only enforced within a process, not across all of them. Now
that Day 2's scaling task actually runs multiple worker containers against
the same domain, this means the *aggregate* request rate to a domain scales
roughly linearly with worker count instead of staying fixed at
`REQUEST_DELAY_SECONDS` -- e.g. 3 workers means up to ~3x the intended rate,
not just "3x more parallel." A Redis-backed shared token bucket would be the
correct fix; see DECISIONS.md's Day 2 scaling entry for why that was deferred
for this project (and why a naive per-worker delay divisor would have made
this worse, not better -- N workers each waiting delay/N independently
produces an N^2, not Nx, over-rate).

Table creation (init_db) is deliberately NOT run at import time -- creating
the engine/sessionmaker here is safe (SQLAlchemy doesn't open a connection
until a query actually runs), but issuing DDL is a real database round trip,
and this module gets imported by tests that have no database available. It
runs instead on Celery's `worker_process_init` signal, which only fires when
an actual worker process boots.
"""

from celery.signals import worker_process_init

from scraper.celery_app import celery_app
from scraper.crawl import crawl_one
from scraper.db import get_engine, get_session_factory, init_db
from scraper.rate_limit import RateLimiter
from scraper.robots import RobotsChecker
from scraper.sites import SITES

_engine = get_engine()
_session_factory = get_session_factory(_engine)

_robots_checker = RobotsChecker()
_rate_limiter = RateLimiter()


@worker_process_init.connect
def _init_db_on_worker_start(**kwargs) -> None:
    init_db(_engine)


@celery_app.task(name="scraper.crawl_url_task")
def crawl_url_task(url: str, site_key: str) -> int | None:
    """Crawls a single URL using the named SITES fetch strategy, storing the
    result via the same crawl_one() pipeline used everywhere else. Returns
    the stored Page's id, or None if robots.txt disallowed the URL.
    """
    session = _session_factory()
    try:
        page = crawl_one(
            url,
            session,
            _robots_checker,
            _rate_limiter,
            fetch_fn=SITES[site_key].fetch_fn,
        )
        return page.id if page is not None else None
    finally:
        session.close()
