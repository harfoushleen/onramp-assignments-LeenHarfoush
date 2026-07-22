"""Multi-page pagination crawl for books.toscrape.com.

Follows the site's own "next" link from listing page to listing page --
rather than assuming a fixed page count -- and stores both each listing page
and every book-detail page it links to, until either the site runs out of
pages or a caller-supplied page limit is reached. Reuses crawl_one() for
every fetch, so robots.txt and per-domain rate limiting apply automatically
without any site-specific politeness logic here.
"""

from collections.abc import Callable, Iterator
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from scraper.crawl import crawl_one
from scraper.db import Page
from scraper.rate_limit import RateLimiter
from scraper.robots import RobotsChecker


def find_next_page_url(html: str, page_url: str) -> str | None:
    """Returns the absolute URL of the "next" listing page, or None on the last page."""
    soup = BeautifulSoup(html, "lxml")
    next_link = soup.select_one("li.next a")
    href = next_link.get("href") if next_link else None
    return urljoin(page_url, href) if href else None


def find_book_detail_urls(html: str, page_url: str) -> list[str]:
    """Returns the absolute URLs of every book's detail page linked from a listing page."""
    soup = BeautifulSoup(html, "lxml")
    return [
        urljoin(page_url, a["href"])
        for a in soup.select("article.product_pod h3 a")
        if a.get("href")
    ]


def crawl_books(
    start_url: str,
    session: Session,
    robots_checker: RobotsChecker,
    rate_limiter: RateLimiter,
    max_pages: int,
    fetch_fn: Callable[[str], str] | None = None,
) -> Iterator[Page]:
    """Yields each stored Page (listing or detail) as it's crawled, up to max_pages.

    Stops early if robots.txt disallows a listing page (crawl_one() returns None
    for it) -- there'd be no HTML to find further links in, so the walk ends
    there. A disallowed *detail* page is just skipped; the listing walk continues.
    """
    stored_count = 0
    current_url: str | None = start_url

    while current_url is not None and stored_count < max_pages:
        listing_page = crawl_one(
            current_url, session, robots_checker, rate_limiter, fetch_fn=fetch_fn
        )
        if listing_page is None:
            break
        stored_count += 1
        yield listing_page

        for detail_url in find_book_detail_urls(listing_page.raw_html, current_url):
            if stored_count >= max_pages:
                break
            detail_page = crawl_one(
                detail_url, session, robots_checker, rate_limiter, fetch_fn=fetch_fn
            )
            if detail_page is None:
                continue
            stored_count += 1
            yield detail_page

        current_url = find_next_page_url(listing_page.raw_html, current_url)
