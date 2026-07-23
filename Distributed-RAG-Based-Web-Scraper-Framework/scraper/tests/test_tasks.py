"""crawl_url_task is a Celery task, but calling it as a plain function (via
`.run()`) executes its body synchronously in-process -- no broker, no Redis,
no real network or database needed. crawl_one() and the session factory are
mocked so this only exercises "does the task wire the right arguments
through", not the pipeline itself (already covered by test_crawl.py).
"""

from unittest.mock import MagicMock, patch

from scraper.sites import SITES
from scraper.tasks import _rate_limiter, _robots_checker, crawl_url_task, process_page_task

URL = "https://quotes.toscrape.com/page/1/"


def test_crawl_url_task_calls_crawl_one_with_expected_arguments():
    fake_session = MagicMock()
    fake_session.query.return_value.filter_by.return_value.first.return_value = None
    fake_page = MagicMock(id=42)

    with (
        patch("scraper.tasks._session_factory", return_value=fake_session),
        patch("scraper.tasks.crawl_one", return_value=fake_page) as mock_crawl_one,
        patch("scraper.tasks.process_page_task.delay") as mock_delay,
    ):
        result = crawl_url_task.run(URL, "quotes_static")

    assert result == 42
    mock_crawl_one.assert_called_once_with(
        URL,
        fake_session,
        _robots_checker,
        _rate_limiter,
        fetch_fn=SITES["quotes_static"].fetch_fn,
    )
    mock_delay.assert_called_once_with(42)
    fake_session.close.assert_called_once()


def test_crawl_url_task_skips_enqueue_when_page_already_processed():
    fake_session = MagicMock()
    fake_session.query.return_value.filter_by.return_value.first.return_value = MagicMock()
    fake_page = MagicMock(id=42)

    with (
        patch("scraper.tasks._session_factory", return_value=fake_session),
        patch("scraper.tasks.crawl_one", return_value=fake_page),
        patch("scraper.tasks.process_page_task.delay") as mock_delay,
    ):
        result = crawl_url_task.run(URL, "quotes_static")

    assert result == 42
    mock_delay.assert_not_called()


def test_crawl_url_task_uses_the_site_configs_own_fetch_strategy():
    fake_session = MagicMock()

    with (
        patch("scraper.tasks._session_factory", return_value=fake_session),
        patch("scraper.tasks.crawl_one", return_value=None) as mock_crawl_one,
        patch("scraper.tasks.process_page_task.delay") as mock_delay,
    ):
        result = crawl_url_task.run("https://quotes.toscrape.com/js/page/1/", "quotes_js")

    assert result is None
    assert mock_crawl_one.call_args.kwargs["fetch_fn"] is SITES["quotes_js"].fetch_fn
    mock_delay.assert_not_called()


def test_crawl_url_task_does_not_enqueue_processing_when_disallowed():
    fake_session = MagicMock()

    with (
        patch("scraper.tasks._session_factory", return_value=fake_session),
        patch("scraper.tasks.crawl_one", return_value=None),
        patch("scraper.tasks.process_page_task.delay") as mock_delay,
    ):
        crawl_url_task.run(URL, "quotes_static")

    mock_delay.assert_not_called()


def test_process_page_task_stores_a_validated_processed_page():
    fake_session = MagicMock()
    fake_session.query.return_value.filter_by.return_value.first.return_value = None
    fake_page = MagicMock(
        id=7, raw_html="<html><body><p>Hi.</p></body></html>", extracted_text="Hi."
    )
    fake_session.get.return_value = fake_page

    stored = {}

    def fake_add(obj):
        stored["obj"] = obj

    fake_session.add.side_effect = fake_add

    with patch("scraper.tasks._session_factory", return_value=fake_session):
        process_page_task.run(7)

    fake_session.get.assert_called_once()
    assert stored["obj"].page_id == 7
    assert stored["obj"].text == "Hi."
    assert stored["obj"].tables == []
    fake_session.commit.assert_called_once()
    fake_session.close.assert_called_once()


def test_process_page_task_skips_when_already_processed():
    fake_session = MagicMock()
    fake_session.query.return_value.filter_by.return_value.first.return_value = MagicMock()

    with patch("scraper.tasks._session_factory", return_value=fake_session):
        result = process_page_task.run(7)

    assert result is None
    fake_session.get.assert_not_called()
    fake_session.add.assert_not_called()


def test_crawl_url_task_closes_session_even_if_crawl_one_raises():
    fake_session = MagicMock()

    with (
        patch("scraper.tasks._session_factory", return_value=fake_session),
        patch("scraper.tasks.crawl_one", side_effect=RuntimeError("boom")),
    ):
        try:
            crawl_url_task.run(URL, "quotes_static")
        except RuntimeError:
            pass

    fake_session.close.assert_called_once()
