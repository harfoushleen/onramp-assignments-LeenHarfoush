"""Walks books.toscrape.com's pagination to discover URLs, then pushes each
one onto the Celery queue as a crawl_url_task job -- storage happens entirely
inside the worker, not here.

Listing pages have to be walked serially: each page's "next" link only comes
from that page's own HTML, so there's an unavoidable discovery step before
anything can be queued. That discovery fetch reuses find_next_page_url() and
find_book_detail_urls() from paginate.py (no new URL-discovery logic), and is
still gated by the same robots check and rate limiter crawl_one() uses --
it's a real request to the real site, just like any other fetch. It does NOT
store the page itself, though: every stored row, listing or detail, is the
result of a crawl_url_task a worker actually ran, not something this script
wrote directly. The cost of that invariant is that each listing page is
fetched twice total across the system (once here to read its links, once by
the worker task that stores it) -- a small, deliberate duplication.
Run with: python -m scraper.enqueue_crawl
"""

import os

from scraper.fetch import USER_AGENT
from scraper.paginate import find_book_detail_urls, find_next_page_url
from scraper.rate_limit import RateLimiter
from scraper.robots import RobotsChecker
from scraper.sites import SITES
from scraper.tasks import crawl_url_task

START_URL = "https://books.toscrape.com/catalogue/page-1.html"
DEFAULT_MAX_PAGES = 300


def _discovery_fetch(
    url: str, robots_checker: RobotsChecker, rate_limiter: RateLimiter
) -> str | None:
    """Fetches a listing page's HTML for link discovery only -- no parsing or
    storage -- but still applies the same politeness checks crawl_one() does.
    """
    if not robots_checker.can_fetch(url, USER_AGENT):
        return None
    rate_limiter.wait(url)
    return SITES["books"].fetch_fn(url)


def discover_and_enqueue(
    start_url: str,
    robots_checker: RobotsChecker,
    rate_limiter: RateLimiter,
    max_pages: int,
) -> int:
    """Walks listing pages from start_url, enqueuing a crawl_url_task for the
    listing page itself and every book-detail URL found on it, up to
    max_pages total jobs enqueued. Returns the number of jobs enqueued.
    """
    enqueued = 0
    current_url: str | None = start_url

    while current_url is not None and enqueued < max_pages:
        html = _discovery_fetch(current_url, robots_checker, rate_limiter)
        if html is None:
            break

        crawl_url_task.delay(current_url, "books")
        enqueued += 1

        for detail_url in find_book_detail_urls(html, current_url):
            if enqueued >= max_pages:
                break
            crawl_url_task.delay(detail_url, "books")
            enqueued += 1

        current_url = find_next_page_url(html, current_url)

    return enqueued


def main() -> None:
    max_pages = int(os.environ.get("BOOKS_MAX_PAGES", DEFAULT_MAX_PAGES))
    enqueued = discover_and_enqueue(START_URL, RobotsChecker(), RateLimiter(), max_pages)
    print(f"Enqueued {enqueued} crawl jobs")


if __name__ == "__main__":
    main()
