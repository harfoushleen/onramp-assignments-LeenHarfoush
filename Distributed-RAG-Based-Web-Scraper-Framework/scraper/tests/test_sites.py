from functools import partial

from scraper.fetch import fetch as fetch_static
from scraper.fetch_js import fetch_rendered
from scraper.sites import SITES, js_site, static_site


def test_static_site_uses_plain_fetch():
    config = static_site("example")
    assert config.fetch_fn is fetch_static


def test_js_site_uses_playwright_fetch_with_selector_bound():
    config = js_site("example", wait_selector=".quote")
    assert isinstance(config.fetch_fn, partial)
    assert config.fetch_fn.func is fetch_rendered
    assert config.fetch_fn.keywords == {"wait_selector": ".quote"}


def test_registry_has_a_static_and_a_js_strategy_for_quotes_site():
    assert SITES["quotes_static"].fetch_fn is fetch_static

    js_fetch_fn = SITES["quotes_js"].fetch_fn
    assert isinstance(js_fetch_fn, partial)
    assert js_fetch_fn.func is fetch_rendered
    assert js_fetch_fn.keywords["wait_selector"] == ".quote"
