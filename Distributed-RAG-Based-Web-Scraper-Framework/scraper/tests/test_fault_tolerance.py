"""Retry/backoff/dead-letter behavior for crawl_url_task and process_page_task.

Uses .apply() (not .delay()) so tasks run synchronously in-process with real
Celery retry/on_failure machinery -- confirmed separately that Celery's
autoretry_for and on_failure work the same way for these class-based tasks
as for the more common @app.task-decorated-function style. No broker or real
DB is needed: _session_factory is mocked so dead-letter writes (and the
crawl/process bodies themselves) never try to hit Postgres.
"""

from unittest.mock import MagicMock, patch

from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from scraper.db import DeadLetterTask
from scraper.fetch import FetchError, RetryableFetchError
from scraper.schemas import ProcessedRecord
from scraper.tasks import crawl_url_task, process_page_task

URL = "https://quotes.toscrape.com/page/1/"


def test_crawl_url_task_retries_a_retryable_fetch_error_and_then_succeeds():
    fake_session = MagicMock()
    fake_session.query.return_value.filter_by.return_value.first.return_value = None
    fake_page = MagicMock(id=42)

    with (
        patch("scraper.tasks._session_factory", return_value=fake_session),
        patch(
            "scraper.tasks.crawl_one",
            side_effect=[RetryableFetchError("timeout"), fake_page],
        ) as mock_crawl_one,
        patch("scraper.tasks.process_page_task.delay"),
        patch("scraper.tasks._write_dead_letter") as mock_dead_letter,
    ):
        async_result = crawl_url_task.apply(args=(URL, "quotes_static"))

    assert async_result.state == "SUCCESS"
    assert async_result.result == 42
    assert mock_crawl_one.call_count == 2
    mock_dead_letter.assert_not_called()


def test_crawl_url_task_exhausts_retries_and_lands_in_dead_letter():
    fake_session = MagicMock()
    fake_session.query.return_value.filter_by.return_value.first.return_value = None

    original_max_retries = crawl_url_task.max_retries
    crawl_url_task.max_retries = 1
    try:
        with (
            patch("scraper.tasks._session_factory", return_value=fake_session),
            patch(
                "scraper.tasks.crawl_one",
                side_effect=RetryableFetchError("still timing out"),
            ) as mock_crawl_one,
        ):
            async_result = crawl_url_task.apply(args=(URL, "quotes_static"))
    finally:
        crawl_url_task.max_retries = original_max_retries

    assert async_result.state == "FAILURE"
    # 1 initial attempt + 1 retry (max_retries=1) = 2 total calls to crawl_one.
    assert mock_crawl_one.call_count == 2

    dead_letter_calls = [
        call for call in fake_session.add.call_args_list if isinstance(call.args[0], DeadLetterTask)
    ]
    assert len(dead_letter_calls) == 1
    row = dead_letter_calls[0].args[0]
    assert row.task_name == "scraper.crawl_url_task"
    assert row.url == URL
    assert "still timing out" in row.error
    assert row.attempt_count == 2
    fake_session.commit.assert_called()


def test_crawl_url_task_non_retryable_fetch_error_fails_immediately():
    fake_session = MagicMock()
    fake_session.query.return_value.filter_by.return_value.first.return_value = None

    with (
        patch("scraper.tasks._session_factory", return_value=fake_session),
        patch(
            "scraper.tasks.crawl_one",
            side_effect=FetchError("404 not found"),
        ) as mock_crawl_one,
    ):
        async_result = crawl_url_task.apply(args=(URL, "quotes_static"))

    assert async_result.state == "FAILURE"
    # A non-retryable FetchError should not trigger any retry attempts.
    assert mock_crawl_one.call_count == 1

    dead_letter_calls = [
        call for call in fake_session.add.call_args_list if isinstance(call.args[0], DeadLetterTask)
    ]
    assert len(dead_letter_calls) == 1
    assert dead_letter_calls[0].args[0].attempt_count == 1


def test_crawl_url_task_robots_disallow_is_not_a_failure_or_retry():
    """Regression test: a robots.txt disallow returns None from crawl_one(),
    it never raises -- confirms fault-tolerance work didn't change that.
    """
    fake_session = MagicMock()
    fake_session.query.return_value.filter_by.return_value.first.return_value = None

    with (
        patch("scraper.tasks._session_factory", return_value=fake_session),
        patch("scraper.tasks.crawl_one", return_value=None) as mock_crawl_one,
        patch("scraper.tasks.process_page_task.delay") as mock_delay,
        patch("scraper.tasks._write_dead_letter") as mock_dead_letter,
    ):
        async_result = crawl_url_task.apply(args=(URL, "quotes_static"))

    assert async_result.state == "SUCCESS"
    assert async_result.result is None
    assert mock_crawl_one.call_count == 1
    mock_delay.assert_not_called()
    mock_dead_letter.assert_not_called()


def test_process_page_task_retries_a_transient_db_error_and_then_succeeds():
    fake_session = MagicMock()
    fake_session.query.return_value.filter_by.return_value.first.return_value = None
    fake_page = MagicMock(id=7, raw_html="<p>Hi.</p>", extracted_text="Hi.")
    fake_session.get.return_value = fake_page

    with (
        patch("scraper.tasks._session_factory", return_value=fake_session),
        patch("scraper.tasks.process_page") as mock_process_page,
        patch("scraper.tasks._write_dead_letter") as mock_dead_letter,
        patch("scraper.tasks.embed_page_task.delay") as mock_embed_delay,
    ):
        mock_process_page.side_effect = [
            OperationalError("stmt", {}, Exception("connection dropped")),
            ProcessedRecord(text="Hi.", tables=[]),
        ]
        async_result = process_page_task.apply(args=(7,))

    assert async_result.state == "SUCCESS"
    assert mock_process_page.call_count == 2
    mock_dead_letter.assert_not_called()
    mock_embed_delay.assert_called_once_with(7)


def test_process_page_task_validation_error_is_non_retryable():
    fake_session = MagicMock()
    fake_session.query.return_value.filter_by.return_value.first.return_value = None
    fake_page = MagicMock(id=7, raw_html="<p>Hi.</p>", extracted_text="Hi.", url="https://x/y")
    fake_session.get.return_value = fake_page

    validation_error = ValidationError.from_exception_data("ProcessedRecord", [])

    with (
        patch("scraper.tasks._session_factory", return_value=fake_session),
        patch("scraper.tasks.process_page", side_effect=validation_error) as mock_process_page,
    ):
        async_result = process_page_task.apply(args=(7,))

    assert async_result.state == "FAILURE"
    assert mock_process_page.call_count == 1

    dead_letter_calls = [
        call for call in fake_session.add.call_args_list if isinstance(call.args[0], DeadLetterTask)
    ]
    assert len(dead_letter_calls) == 1
    assert dead_letter_calls[0].args[0].attempt_count == 1
