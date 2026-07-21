from unittest.mock import patch

import pytest

from scraper.rate_limit import RateLimiter


def test_wait_sleeps_remaining_delay_for_repeat_request_to_same_domain():
    limiter = RateLimiter(delay_seconds=2.0)

    # monotonic() is called once on the first wait() (just records a timestamp),
    # then twice on the second wait() (once to compute elapsed, once to re-record).
    with (
        patch("scraper.rate_limit.time.monotonic", side_effect=[100.0, 100.5, 100.5]),
        patch("scraper.rate_limit.time.sleep") as mock_sleep,
    ):
        limiter.wait("https://example.com/a")
        limiter.wait("https://example.com/b")

    mock_sleep.assert_called_once()
    slept_for = mock_sleep.call_args[0][0]
    assert slept_for == pytest.approx(1.5)


def test_wait_does_not_sleep_once_delay_has_already_elapsed():
    limiter = RateLimiter(delay_seconds=1.0)

    with (
        patch("scraper.rate_limit.time.monotonic", side_effect=[100.0, 102.0, 102.0]),
        patch("scraper.rate_limit.time.sleep") as mock_sleep,
    ):
        limiter.wait("https://example.com/a")
        limiter.wait("https://example.com/b")

    mock_sleep.assert_not_called()


def test_wait_is_independent_per_domain():
    limiter = RateLimiter(delay_seconds=100.0)

    with (
        patch("scraper.rate_limit.time.monotonic", return_value=100.0),
        patch("scraper.rate_limit.time.sleep") as mock_sleep,
    ):
        limiter.wait("https://example.com/a")
        limiter.wait("https://other.com/a")

    mock_sleep.assert_not_called()


def test_default_delay_reads_from_env_var(monkeypatch):
    monkeypatch.setenv("REQUEST_DELAY_SECONDS", "3.5")
    limiter = RateLimiter()
    assert limiter.delay_seconds == 3.5
