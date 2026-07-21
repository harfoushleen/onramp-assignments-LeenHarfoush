"""Manual proof that fetch -> parse -> store works end to end.

Crawls the 10 listing pages of quotes.toscrape.com (a public scraping-practice
site with no robots.txt restrictions) and prints one line per stored row.
Run with: python -m scraper.demo
"""

import logging

from scraper.crawl import crawl_one
from scraper.db import get_engine, get_session_factory, init_db
from scraper.rate_limit import RateLimiter
from scraper.robots import RobotsChecker

BASE_URL = "https://quotes.toscrape.com"
PAGE_COUNT = 10


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    engine = get_engine()
    init_db(engine)
    session = get_session_factory(engine)()

    robots_checker = RobotsChecker()
    rate_limiter = RateLimiter()

    for page_number in range(1, PAGE_COUNT + 1):
        url = f"{BASE_URL}/page/{page_number}/"
        page = crawl_one(url, session, robots_checker, rate_limiter)
        if page is None:
            print(f"[{page_number:02d}] {url} -> skipped (robots.txt disallow)")
            continue
        print(f"[{page_number:02d}] {url} -> id={page.id} hash={page.content_hash[:12]} "
              f"text_len={len(page.extracted_text)}")

    session.close()


if __name__ == "__main__":
    main()
