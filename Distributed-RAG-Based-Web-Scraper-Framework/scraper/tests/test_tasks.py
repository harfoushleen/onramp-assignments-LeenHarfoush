"""crawl_url_task is a Celery task, but calling it as a plain function (via
`.run()`) executes its body synchronously in-process -- no broker, no Redis,
no real network or database needed. crawl_one() and the session factory are
mocked so this only exercises "does the task wire the right arguments
through", not the pipeline itself (already covered by test_crawl.py).
"""

from unittest.mock import MagicMock, patch

from scraper.sites import SITES
from scraper.tasks import _rate_limiter, _robots_checker, crawl_url_task

URL = "https://quotes.toscrape.com/page/1/"


def test_crawl_url_task_calls_crawl_one_with_expected_arguments():
    fake_session = MagicMock()
    fake_page = MagicMock(id=42)

    with (
        patch("scraper.tasks._session_factory", return_value=fake_session),
        patch("scraper.tasks.crawl_one", return_value=fake_page) as mock_crawl_one,
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
    fake_session.close.assert_called_once()


def test_crawl_url_task_uses_the_site_configs_own_fetch_strategy():
    fake_session = MagicMock()

    with (
        patch("scraper.tasks._session_factory", return_value=fake_session),
        patch("scraper.tasks.crawl_one", return_value=None) as mock_crawl_one,
    ):
        result = crawl_url_task.run("https://quotes.toscrape.com/js/page/1/", "quotes_js")

    assert result is None
    assert mock_crawl_one.call_args.kwargs["fetch_fn"] is SITES["quotes_js"].fetch_fn


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
