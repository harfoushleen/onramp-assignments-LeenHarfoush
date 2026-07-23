"""Manual proof that re-crawling a URL only inserts a new row when its
content actually changed.

Part 1 crawls a real URL twice in a row (real content, unchanged between
calls) and confirms only one row lands. Part 2 proves the "content changed"
path is real, not just described: it directly mutates the stored row's
content_hash to a value we know is wrong, then re-crawls the same real URL
again -- since crawl_one() compares against that (now-deliberately-stale)
hash, it sees a mismatch and inserts a genuine new row via the same code path
a real content change would trigger. What's simulated is the *old* hash;
the detection-and-insert logic that runs afterward is exactly the real code.

Run with: python -m scraper.demo_versioning
"""

import logging

from scraper.crawl import crawl_one
from scraper.db import Page, get_engine, get_latest_page, get_session_factory, init_db
from scraper.rate_limit import RateLimiter
from scraper.robots import RobotsChecker

URL = "https://quotes.toscrape.com/page/1/"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    engine = get_engine()
    init_db(engine)
    session = get_session_factory(engine)()

    robots_checker = RobotsChecker()
    rate_limiter = RateLimiter(delay_seconds=0.5)

    print("--- Part 1: re-crawl the same real URL twice, content unchanged ---")
    first = crawl_one(URL, session, robots_checker, rate_limiter)
    print(f"crawl #1 -> id={first.id} hash={first.content_hash[:12]}")

    second = crawl_one(URL, session, robots_checker, rate_limiter)
    print(f"crawl #2 -> id={second.id} hash={second.content_hash[:12]}")

    row_count = session.query(Page).filter(Page.url == URL).count()
    print(f"rows stored for this URL so far: {row_count} (expected 1 -- no duplicate)")

    print("\n--- Part 2: simulate a genuine content change ---")
    print("manually corrupting the stored content_hash to force a mismatch on re-crawl...")
    latest = get_latest_page(session, URL)
    latest.content_hash = "0" * 64  # deliberately wrong, simulates "the old version differed"
    session.commit()

    third = crawl_one(URL, session, robots_checker, rate_limiter)
    print(f"crawl #3 (after simulated change) -> id={third.id} hash={third.content_hash[:12]}")

    row_count = session.query(Page).filter(Page.url == URL).count()
    print(f"rows stored for this URL now: {row_count} (expected 2 -- a real new version)")

    latest = get_latest_page(session, URL)
    print(f"get_latest_page() returns id={latest.id}, matching crawl #3's id={third.id}: "
          f"{latest.id == third.id}")

    session.close()


if __name__ == "__main__":
    main()
