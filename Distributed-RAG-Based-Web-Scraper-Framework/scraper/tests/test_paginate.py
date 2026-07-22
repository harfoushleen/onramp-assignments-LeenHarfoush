from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from scraper.db import Base
from scraper.paginate import crawl_books, find_book_detail_urls, find_next_page_url
from scraper.rate_limit import RateLimiter

LISTING_PAGE_1_HTML = """
<html><body>
<ol>
  <li><article class="product_pod">
    <h3><a href="book-a_1/index.html" title="Book A">Book A</a></h3>
  </article></li>
  <li><article class="product_pod">
    <h3><a href="book-b_2/index.html" title="Book B">Book B</a></h3>
  </article></li>
</ol>
<ul class="pager"><li class="next"><a href="page-2.html">next</a></li></ul>
</body></html>
"""

LISTING_PAGE_2_HTML = """
<html><body>
<ol>
  <li><article class="product_pod">
    <h3><a href="book-c_3/index.html" title="Book C">Book C</a></h3>
  </article></li>
</ol>
<ul class="pager"></ul>
</body></html>
"""

DETAIL_HTML = "<html><body><p>Some book description.</p></body></html>"

PAGE_1_URL = "https://example.com/catalogue/page-1.html"
PAGE_2_URL = "https://example.com/catalogue/page-2.html"
BOOK_A_URL = "https://example.com/catalogue/book-a_1/index.html"
BOOK_B_URL = "https://example.com/catalogue/book-b_2/index.html"
BOOK_C_URL = "https://example.com/catalogue/book-c_3/index.html"

FIXTURES = {
    PAGE_1_URL: LISTING_PAGE_1_HTML,
    PAGE_2_URL: LISTING_PAGE_2_HTML,
    BOOK_A_URL: DETAIL_HTML,
    BOOK_B_URL: DETAIL_HTML,
    BOOK_C_URL: DETAIL_HTML,
}


class FakeRobots:
    def can_fetch(self, url: str, user_agent: str = "*") -> bool:
        return True


def fake_fetch(url: str) -> str:
    return FIXTURES[url]


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_find_next_page_url_resolves_relative_href():
    assert find_next_page_url(LISTING_PAGE_1_HTML, PAGE_1_URL) == PAGE_2_URL


def test_find_next_page_url_returns_none_on_last_page():
    assert find_next_page_url(LISTING_PAGE_2_HTML, PAGE_2_URL) is None


def test_find_book_detail_urls_resolves_relative_hrefs():
    assert find_book_detail_urls(LISTING_PAGE_1_HTML, PAGE_1_URL) == [BOOK_A_URL, BOOK_B_URL]


def test_crawl_books_follows_pagination_until_no_next_link():
    session = make_session()
    pages = list(
        crawl_books(
            PAGE_1_URL, session, FakeRobots(), RateLimiter(delay_seconds=0),
            max_pages=10, fetch_fn=fake_fetch,
        )
    )

    assert [p.url for p in pages] == [PAGE_1_URL, BOOK_A_URL, BOOK_B_URL, PAGE_2_URL, BOOK_C_URL]


def test_crawl_books_stops_at_max_pages_even_mid_listing():
    session = make_session()
    pages = list(
        crawl_books(
            PAGE_1_URL, session, FakeRobots(), RateLimiter(delay_seconds=0),
            max_pages=2, fetch_fn=fake_fetch,
        )
    )

    assert [p.url for p in pages] == [PAGE_1_URL, BOOK_A_URL]
