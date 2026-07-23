import logging
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from scraper.crawl import content_hash, crawl_one
from scraper.db import Base, Page, get_latest_page
from scraper.rate_limit import RateLimiter

SAMPLE_HTML = "<html><head><title>T</title></head><body><p>Hi there.</p></body></html>"
CHANGED_HTML = (
    "<html><head><title>T</title></head><body><p>Something different now.</p></body></html>"
)


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


def test_crawl_one_uses_injected_fetch_fn():
    session = make_session()
    calls = []

    def fake_js_fetch(url: str) -> str:
        calls.append(url)
        return SAMPLE_HTML

    with patch("scraper.crawl.fetch", side_effect=AssertionError("should not use default fetch")):
        page = crawl_one(
            "https://example.com/rendered",
            session,
            FakeRobots(allowed=True),
            RateLimiter(delay_seconds=0),
            fetch_fn=fake_js_fetch,
        )

    assert calls == ["https://example.com/rendered"]
    assert page.extracted_text == "Hi there."


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


def test_crawl_one_skips_insert_when_content_unchanged(caplog):
    session = make_session()
    url = "https://example.com/versioned"

    with patch("scraper.crawl.fetch", return_value=SAMPLE_HTML):
        first = crawl_one(url, session, FakeRobots(), RateLimiter(delay_seconds=0))
        with caplog.at_level(logging.INFO, logger="scraper.crawl"):
            second = crawl_one(url, session, FakeRobots(), RateLimiter(delay_seconds=0))

    assert session.query(Page).filter(Page.url == url).count() == 1
    assert second.id == first.id
    assert "content unchanged" in caplog.text


def test_crawl_one_inserts_new_version_when_content_changes():
    session = make_session()
    url = "https://example.com/versioned"

    with patch("scraper.crawl.fetch", return_value=SAMPLE_HTML):
        first = crawl_one(url, session, FakeRobots(), RateLimiter(delay_seconds=0))
    with patch("scraper.crawl.fetch", return_value=CHANGED_HTML):
        second = crawl_one(url, session, FakeRobots(), RateLimiter(delay_seconds=0))

    assert session.query(Page).filter(Page.url == url).count() == 2
    assert second.id != first.id
    assert second.content_hash != first.content_hash


def test_get_latest_page_returns_none_for_unknown_url():
    session = make_session()
    assert get_latest_page(session, "https://example.com/never-crawled") is None


def test_get_latest_page_returns_most_recently_stored_version():
    session = make_session()
    url = "https://example.com/versioned"

    with patch("scraper.crawl.fetch", return_value=SAMPLE_HTML):
        crawl_one(url, session, FakeRobots(), RateLimiter(delay_seconds=0))
    with patch("scraper.crawl.fetch", return_value=CHANGED_HTML):
        second = crawl_one(url, session, FakeRobots(), RateLimiter(delay_seconds=0))

    latest = get_latest_page(session, url)
    assert latest.id == second.id
    assert latest.content_hash == second.content_hash
