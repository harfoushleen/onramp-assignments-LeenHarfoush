"""Playwright launches a real headless browser, so these are opt-in only
(RUN_BROWSER_TESTS=1) and hit the live quotes.toscrape.com/js/ page -- not run
in CI, which has no browser binaries installed. The strategy-selection logic
these fetches feed into (sites.py, crawl_one's fetch_fn) is covered by the
regular, CI-safe unit tests.
"""

import os

import pytest

from scraper.fetch_js import fetch_rendered

requires_browser = pytest.mark.skipif(
    os.environ.get("RUN_BROWSER_TESTS") != "1",
    reason="set RUN_BROWSER_TESTS=1 to run real-browser Playwright tests",
)


@pytest.mark.browser
@requires_browser
def test_fetch_rendered_returns_html_containing_quotes():
    html = fetch_rendered("https://quotes.toscrape.com/js/", wait_selector=".quote")
    assert ".quote" not in html  # sanity: selector isn't literally in the markup
    assert "quote" in html.lower()
    assert "<div" in html


@pytest.mark.browser
@requires_browser
def test_fetch_rendered_times_out_on_a_selector_that_never_appears():
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    with pytest.raises(PlaywrightTimeoutError):
        fetch_rendered(
            "https://quotes.toscrape.com/js/",
            wait_selector=".this-selector-does-not-exist",
            timeout_ms=2_000,
        )
