"""Single-URL crawl pipeline: robots check -> rate limit -> fetch -> parse -> store."""

import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from scraper.db import Page
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
) -> Page | None:
    """Returns the stored Page, or None if robots.txt disallows the URL.

    A disallow is a normal, expected outcome of politely crawling the web -- not
    an error -- so it's signaled by a None return rather than an exception.
    """
    if not robots_checker.can_fetch(url, user_agent):
        logger.info("skipping %s: disallowed by robots.txt", url)
        return None

    rate_limiter.wait(url)
    html = fetch(url)
    parsed = parse(html)

    page = Page(
        url=url,
        raw_html=html,
        extracted_text=parsed["text"],
        content_hash=content_hash(parsed["text"]),
        fetched_at=datetime.now(UTC),
    )
    session.add(page)
    session.commit()
    return page
