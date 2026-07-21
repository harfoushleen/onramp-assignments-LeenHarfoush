import logging
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from scraper.crawl import content_hash, crawl_one
from scraper.db import Base, Page
from scraper.rate_limit import RateLimiter

SAMPLE_HTML = "<html><head><title>T</title></head><body><p>Hi there.</p></body></html>"


class FakeRobots:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed

    def can_fetch(self, url: str, user_agent: str = "*") -> bool:
        return self.allowed


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_crawl_one_stores_a_row():
    session = make_session()
    with patch("scraper.crawl.fetch", return_value=SAMPLE_HTML):
        page = crawl_one(
            "https://example.com/page1",
            session,
            FakeRobots(allowed=True),
            RateLimiter(delay_seconds=0),
        )

    assert page.id is not None
    assert page.url == "https://example.com/page1"
    assert page.content_hash == content_hash(page.extracted_text)
    assert session.query(Page).count() == 1


def test_crawl_one_skips_disallowed_url_without_raising(caplog):
    session = make_session()
    with caplog.at_level(logging.INFO, logger="scraper.crawl"):
        result = crawl_one(
            "https://example.com/blocked",
            session,
            FakeRobots(allowed=False),
            RateLimiter(delay_seconds=0),
        )

    assert result is None
    assert session.query(Page).count() == 0
    assert "disallowed by robots.txt" in caplog.text
