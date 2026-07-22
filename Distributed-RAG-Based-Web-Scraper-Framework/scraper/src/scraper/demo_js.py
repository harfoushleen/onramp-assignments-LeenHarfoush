"""Manual proof that the Playwright fetch strategy works end to end.

Crawls a few pages of quotes.toscrape.com/js/ (the JS-rendered variant of the
same practice site used in demo.py) using SITES["quotes_js"], then re-crawls
the same page numbers via SITES["quotes_static"] against the plain /page/N/
URLs and compares extracted text.

The two variants serve the same quotes but are NOT byte-identical: the /js/
template omits the " (about)" link text on each quote and swaps the "Top Ten
tags" sidebar for a footer credit line -- that's the site's own JS template,
not a bug in our fetch/parse pipeline (confirmed by inspecting each page's
raw HTML directly). So instead of an exact-match boolean, this reports how
much of each page's text is a shared prefix -- which for these pages runs
through the entire quote/author/tag content and only diverges at that
trailing chrome, which is exactly what we want to see.
Run with: python -m scraper.demo_js
"""

import logging

from scraper.crawl import crawl_one
from scraper.db import get_engine, get_session_factory, init_db
from scraper.rate_limit import RateLimiter
from scraper.robots import RobotsChecker
from scraper.sites import SITES

BASE_URL = "https://quotes.toscrape.com"
PAGE_COUNT = 3


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    engine = get_engine()
    init_db(engine)
    session = get_session_factory(engine)()

    robots_checker = RobotsChecker()
    rate_limiter = RateLimiter()

    for page_number in range(1, PAGE_COUNT + 1):
        js_url = f"{BASE_URL}/js/page/{page_number}/"
        static_url = f"{BASE_URL}/page/{page_number}/"

        js_page = crawl_one(
            js_url, session, robots_checker, rate_limiter,
            fetch_fn=SITES["quotes_js"].fetch_fn,
        )
        static_page = crawl_one(
            static_url, session, robots_checker, rate_limiter,
            fetch_fn=SITES["quotes_static"].fetch_fn,
        )

        if js_page is None or static_page is None:
            print(f"[{page_number:02d}] skipped (robots.txt disallow)")
            continue

        # Normalize the one known, expected chrome difference (see module docstring)
        # so the comparison reflects quote/author/tag content, not that artifact.
        js_text = js_page.extracted_text
        static_text = static_page.extracted_text.replace(" (about)", "")

        shared_prefix_len = _common_prefix_len(js_text, static_text)
        shorter_len = min(len(js_text), len(static_text))
        overlap_pct = 100 * shared_prefix_len / shorter_len if shorter_len else 0
        print(
            f"[{page_number:02d}] js_hash={js_page.content_hash[:12]} "
            f"static_hash={static_page.content_hash[:12]} "
            f"shared_prefix={shared_prefix_len}/{shorter_len} chars ({overlap_pct:.0f}%)"
        )

    session.close()


def _common_prefix_len(a: str, b: str) -> int:
    length = 0
    for char_a, char_b in zip(a, b, strict=False):
        if char_a != char_b:
            break
        length += 1
    return length


if __name__ == "__main__":
    main()
