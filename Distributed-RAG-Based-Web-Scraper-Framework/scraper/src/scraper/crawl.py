"""Single-URL crawl pipeline: robots check -> rate limit -> fetch -> parse -> store."""

import hashlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from scraper.db import Page, get_latest_page
from scraper.fetch import USER_AGENT, fetch
from scraper.parse import parse
from scraper.rate_limit import RateLimiter
from scraper.robots import RobotsChecker

logger = logging.getLogger(__name__)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def crawl_one(
    url: str,
    session: Session,
    robots_checker: RobotsChecker,
    rate_limiter: RateLimiter,
    user_agent: str = USER_AGENT,
    fetch_fn: Callable[[str], str] | None = None,
) -> Page | None:
    """Returns the stored Page, or None if robots.txt disallows the URL.

    A disallow is a normal, expected outcome of politely crawling the web -- not
    an error -- so it's signaled by a None return rather than an exception.

    `fetch_fn` picks the fetch strategy for this URL's site (plain HTTP vs.
    Playwright rendering, see sites.py); defaults to the plain HTTP fetch so
    existing callers don't need to change.
    """
    if not robots_checker.can_fetch(url, user_agent):
        logger.info("skipping %s: disallowed by robots.txt", url)
        return None

    rate_limiter.wait(url)
    fetcher = fetch_fn or fetch
    html = fetcher(url)
    parsed = parse(html)
    new_hash = content_hash(parsed["text"])

    latest = get_latest_page(session, url)
    if latest is not None and latest.content_hash == new_hash:
        logger.info("content unchanged for %s, skipping new version", url)
        return latest

    page = Page(
        url=url,
        raw_html=html,
        extracted_text=parsed["text"],
        content_hash=new_hash,
        fetched_at=datetime.now(UTC),
    )
    session.add(page)
    session.commit()
    return page
