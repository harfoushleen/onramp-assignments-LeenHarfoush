"""Normalization step: turns an already-stored Page (raw_html + extracted_text
from parse()) into a validated ProcessedRecord.

Deliberately does not re-strip raw_html for the free-text content -- parse()
already did that work and it's sitting in extracted_text. The only new
extraction here is structured content parse() throws away: HTML tables (e.g.
the product-info table on a books.toscrape.com detail page), which flatten
into meaningless run-on text if you only ever collapse a page to
get_text().
"""

from bs4 import BeautifulSoup

from scraper.db import Page
from scraper.schemas import ProcessedRecord


def extract_tables(html: str) -> list[dict[str, str]]:
    """Returns one dict per <table> found, mapping each row's header cell to
    its value cell (th/td pairs, as used by books.toscrape.com's product-info
    table: UPC, price, tax, availability, review count, etc). Tables that
    don't follow a th/td-per-row shape contribute no entries.
    """
    soup = BeautifulSoup(html, "lxml")
    tables = []
    for table in soup.find_all("table"):
        row_data: dict[str, str] = {}
        for row in table.find_all("tr"):
            header = row.find("th")
            cell = row.find("td")
            if header is not None and cell is not None:
                row_data[header.get_text(strip=True)] = cell.get_text(strip=True)
        if row_data:
            tables.append(row_data)
    return tables


def process_page(page: Page) -> ProcessedRecord:
    """Builds the normalized record for a stored Page. Quote pages (no
    tables in the HTML) end up with an empty `tables` list; book detail pages
    get their product-info table as structured key-value data alongside the
    free-text description.
    """
    return ProcessedRecord(
        text=page.extracted_text,
        tables=extract_tables(page.raw_html),
    )
