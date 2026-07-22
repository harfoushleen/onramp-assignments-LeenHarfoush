"""JavaScript-rendered page fetch using Playwright (headless Chromium).

Kept in its own module, separate from fetch.py, so the plain-HTTP path never
imports Playwright -- only sites configured for JS rendering pay the cost of
spinning up a browser.
"""

from playwright.sync_api import sync_playwright

DEFAULT_TIMEOUT_MS = 10_000


def fetch_rendered(url: str, wait_selector: str, timeout_ms: float = DEFAULT_TIMEOUT_MS) -> str:
    """Render `url` in headless Chromium and return the DOM HTML once `wait_selector`
    is present, rather than trusting a fixed sleep to be long enough (or too long).
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            # "domcontentloaded" rather than the default "load": the latter waits for
            # every subresource (including third-party CDN scripts) to finish, so a
            # single slow/blocked asset can time out navigation even though the DOM
            # content we actually care about is already present. wait_for_selector
            # below is what actually confirms the content we need has rendered.
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            page.wait_for_selector(wait_selector, timeout=timeout_ms)
            html = page.content()
        finally:
            browser.close()
    return html
