"""Per-site fetch-strategy configuration.

Each target site declares up front how it should be fetched -- plain HTTP for
static HTML, Playwright for JS-rendered content -- rather than the crawler
guessing at crawl time. Add a SiteConfig entry here when onboarding a new
target site; crawl_one() just takes whichever fetch_fn the caller passes in.
"""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from scraper.fetch import fetch as fetch_static
from scraper.fetch_js import fetch_rendered


@dataclass(frozen=True)
class SiteConfig:
    name: str
    fetch_fn: Callable[[str], str]


def static_site(name: str) -> SiteConfig:
    return SiteConfig(name=name, fetch_fn=fetch_static)


def js_site(name: str, wait_selector: str) -> SiteConfig:
    return SiteConfig(name=name, fetch_fn=partial(fetch_rendered, wait_selector=wait_selector))


SITES: dict[str, SiteConfig] = {
    "quotes_static": static_site("quotes.toscrape.com (static)"),
    "quotes_js": js_site("quotes.toscrape.com (JS-rendered)", wait_selector=".quote"),
    "books": static_site("books.toscrape.com (static, paginated)"),
}
