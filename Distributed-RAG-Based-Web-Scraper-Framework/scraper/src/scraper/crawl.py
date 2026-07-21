"""Single-URL crawl pipeline: robots check -> rate limit -> fetch -> parse -> store."""

import hashlib
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from scraper.db import Page
from scraper.fetch import fetch
from scraper.parse import parse
from scraper.rate_limit import RateLimiter
from scraper.robots import RobotsChecker


class RobotsDisallowedError(Exception):
    pass


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def crawl_one(
    url: str,
    session: Session,
    robots_checker: RobotsChecker,
    rate_limiter: RateLimiter,
    user_agent: str = "*",
) -> Page:
    if not robots_checker.can_fetch(url, user_agent):
        raise RobotsDisallowedError(f"robots.txt disallows fetching {url}")

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
