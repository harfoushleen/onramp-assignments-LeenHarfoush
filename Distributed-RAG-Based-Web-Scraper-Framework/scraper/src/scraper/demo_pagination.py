"""Manual proof that pagination crawling works end to end against a real,
large paginated site (books.toscrape.com): follows listing pages' "next"
links and stores each listing page plus every book-detail page it links to,
up to BOOKS_MAX_PAGES. Prints progress as it goes and a final count/timing
summary -- the timing is the single-worker baseline we'll compare
multi-worker runs against later.
Run with: python -m scraper.demo_pagination
"""

import logging
import os
import time

from scraper.db import get_engine, get_session_factory, init_db
from scraper.paginate import crawl_books
from scraper.rate_limit import RateLimiter
from scraper.robots import RobotsChecker
from scraper.sites import SITES

START_URL = "https://books.toscrape.com/catalogue/page-1.html"
DEFAULT_MAX_PAGES = 300


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    max_pages = int(os.environ.get("BOOKS_MAX_PAGES", DEFAULT_MAX_PAGES))

    engine = get_engine()
    init_db(engine)
    session = get_session_factory(engine)()

    robots_checker = RobotsChecker()
    rate_limiter = RateLimiter()

    started_at = time.monotonic()
    stored = 0
    for page in crawl_books(
        START_URL, session, robots_checker, rate_limiter, max_pages,
        fetch_fn=SITES["books"].fetch_fn,
    ):
        stored += 1
        print(f"page {stored}/{max_pages} stored: {page.url}")

    elapsed = time.monotonic() - started_at
    print(f"\nDone: {stored} pages stored in {elapsed:.1f}s")

    session.close()


if __name__ == "__main__":
    main()
