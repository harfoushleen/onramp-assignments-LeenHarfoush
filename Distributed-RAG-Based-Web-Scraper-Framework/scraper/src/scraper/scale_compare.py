"""Times a full books.toscrape.com crawl from enqueue to completion, for
comparing single-worker vs. `--scale scraper=N` wall-clock time.

Truncates the `pages` table first so each run starts from zero, enqueues the
same crawl `enqueue_crawl.py` does, then polls Postgres until every enqueued
job has produced a row -- timing the whole thing with time.monotonic(), the
same approach demo_pagination.py already uses for its single-process timing.

Run against docker-compose's host-exposed ports (Postgres on 5434, Redis on
6380), after starting the stack with the worker count you want to test:

    docker compose up -d postgres redis

    # single-worker baseline
    docker compose up -d --build scraper

    # PowerShell: $env:DATABASE_URL = "postgresql+psycopg://rag:rag@localhost:5434/rag_scraper"
    #             $env:REDIS_URL = "redis://localhost:6380/0"
    #             $env:BOOKS_MAX_PAGES = "300"
    # Bash:       export DATABASE_URL="postgresql+psycopg://rag:rag@localhost:5434/rag_scraper"
    #             export REDIS_URL="redis://localhost:6380/0"
    #             export BOOKS_MAX_PAGES=300
    python -m scraper.scale_compare

    # then, for the 3-worker run:
    docker compose up -d --build --scale scraper=3 scraper
    python -m scraper.scale_compare

Note: each worker keeps its own in-process rate-limiter clock (see
rate_limit.py's module docstring), so with N workers the aggregate request
rate to books.toscrape.com during this comparison is up to ~Nx the
single-worker rate, not just "Nx more parallel." That's a known, documented
tradeoff (see DECISIONS.md's Day 2 scaling entry) -- it's also exactly what
lets this comparison show a real wall-clock speedup, since a shared limiter
that preserved the aggregate rate exactly would eliminate any speedup for a
single-domain crawl.
"""

import os
import time

from sqlalchemy import text

from scraper.db import get_engine
from scraper.enqueue_crawl import START_URL, discover_and_enqueue
from scraper.rate_limit import RateLimiter
from scraper.robots import RobotsChecker

POLL_SECONDS = 2.0


def main() -> None:
    max_pages = int(os.environ.get("BOOKS_MAX_PAGES", 300))
    engine = get_engine()

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE pages"))

    start = time.monotonic()
    enqueued = discover_and_enqueue(START_URL, RobotsChecker(), RateLimiter(), max_pages)
    print(f"Enqueued {enqueued} crawl jobs; waiting for workers to drain the queue...")

    stored = 0
    while stored < enqueued:
        time.sleep(POLL_SECONDS)
        with engine.connect() as conn:
            stored = conn.execute(text("SELECT COUNT(*) FROM pages")).scalar_one()

    elapsed = time.monotonic() - start
    print(f"{stored} pages stored in {elapsed:.1f}s ({elapsed / stored:.2f}s/page)")


if __name__ == "__main__":
    main()
