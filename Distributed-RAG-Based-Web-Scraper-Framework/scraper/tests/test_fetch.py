"""fetch() must correctly decode UTF-8 page bodies even when the server's
Content-Type header omits a charset -- requests silently falls back to
ISO-8859-1 in that case (an old RFC 2616 default), which doesn't raise an
error, it just produces mojibake (e.g. "£" -> "Â£"). See DECISIONS.md for
the incident this regression-tests: books.toscrape.com/quotes.toscrape.com
both send `Content-Type: text/html` with no charset, and their actual
bytes are UTF-8.
"""

from unittest.mock import patch

import requests
from requests.utils import get_encoding_from_headers

from scraper.fetch import fetch


def _fake_response(content: bytes, content_type: str) -> requests.Response:
    """Builds a real requests.Response (not a mock) so response.encoding
    and response.apparent_encoding behave exactly as they would for a real
    HTTP response -- get_encoding_from_headers() is the same function
    requests' own HTTPAdapter calls to set response.encoding in the first
    place.
    """
    response = requests.Response()
    response.status_code = 200
    response.headers["Content-Type"] = content_type
    response.encoding = get_encoding_from_headers(response.headers)
    response._content = content
    return response


def test_fetch_correctly_decodes_utf8_when_content_type_has_no_charset():
    body = "<html><body><p>Price: £51.77</p></body></html>".encode()
    fake_response = _fake_response(body, "text/html")

    with patch("scraper.fetch.requests.get", return_value=fake_response):
        html = fetch("https://example.com")

    assert "£51.77" in html
    assert "Â£" not in html


def test_fetch_respects_an_explicit_non_utf8_charset_declared_by_the_server():
    body = "<html><body><p>Café</p></body></html>".encode("iso-8859-1")
    fake_response = _fake_response(body, "text/html; charset=iso-8859-1")

    with patch("scraper.fetch.requests.get", return_value=fake_response):
        html = fetch("https://example.com")

    assert "Café" in html
