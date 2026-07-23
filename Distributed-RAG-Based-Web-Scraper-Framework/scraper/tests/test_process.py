import pytest
from pydantic import ValidationError

from scraper.db import Page
from scraper.process import extract_tables, process_page
from scraper.schemas import ProcessedRecord

# Canned excerpt of a books.toscrape.com detail page: description paragraph +
# the product-info table (th/td pairs), same shape as the real site.
BOOK_DETAIL_HTML = """
<html><body>
<div id="product_description"></div>
<p>A gripping tale of scraping and structured data.</p>
<table class="table table-striped">
  <tr><th>UPC</th><td>a897fe39b1053632</td></tr>
  <tr><th>Product Type</th><td>Books</td></tr>
  <tr><th>Price (excl. tax)</th><td>&pound;51.77</td></tr>
  <tr><th>Price (incl. tax)</th><td>&pound;51.77</td></tr>
  <tr><th>Tax</th><td>&pound;0.00</td></tr>
  <tr><th>Availability</th><td>In stock (22 available)</td></tr>
  <tr><th>Number of reviews</th><td>0</td></tr>
</table>
</body></html>
"""

QUOTE_PAGE_HTML = """
<html><body>
<div class="quote">
  <span class="text">"Some quote."</span>
  <small class="author">Someone</small>
</div>
</body></html>
"""


def test_extract_tables_returns_key_value_pairs_from_book_detail_html():
    tables = extract_tables(BOOK_DETAIL_HTML)

    assert tables == [
        {
            "UPC": "a897fe39b1053632",
            "Product Type": "Books",
            "Price (excl. tax)": "£51.77",
            "Price (incl. tax)": "£51.77",
            "Tax": "£0.00",
            "Availability": "In stock (22 available)",
            "Number of reviews": "0",
        }
    ]


def test_extract_tables_returns_empty_list_for_quote_page_with_no_table():
    assert extract_tables(QUOTE_PAGE_HTML) == []


def test_process_page_builds_valid_record_with_table_for_book_detail_page():
    page = Page(
        url="https://books.toscrape.com/catalogue/some-book/index.html",
        raw_html=BOOK_DETAIL_HTML,
        extracted_text="A gripping tale of scraping and structured data. UPC ...",
        content_hash="deadbeef",
    )

    record = process_page(page)

    assert isinstance(record, ProcessedRecord)
    assert record.text == page.extracted_text
    assert record.tables[0]["UPC"] == "a897fe39b1053632"


def test_process_page_builds_record_with_no_tables_for_quote_page():
    page = Page(
        url="https://quotes.toscrape.com/page/1/",
        raw_html=QUOTE_PAGE_HTML,
        extracted_text='"Some quote." Someone',
        content_hash="deadbeef",
    )

    record = process_page(page)

    assert record.tables == []
    assert record.text == page.extracted_text


def test_processed_record_rejects_empty_text():
    with pytest.raises(ValidationError):
        ProcessedRecord(text="", tables=[])


def test_processed_record_rejects_malformed_table_shape():
    with pytest.raises(ValidationError):
        ProcessedRecord(text="valid text", tables=[{"key": 123}])  # value must be a string


def test_processed_record_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        ProcessedRecord(text="valid text", tables=[], unexpected="nope")


def test_processed_record_accepts_valid_record_with_no_tables():
    record = ProcessedRecord(text="valid text")
    assert record.tables == []
