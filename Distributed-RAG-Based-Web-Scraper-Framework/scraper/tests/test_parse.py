from unittest.mock import MagicMock, patch

from scraper.fetch import fetch
from scraper.parse import parse

SAMPLE_HTML = """
<html>
<head><title>Test Page</title></head>
<body>
<script>var x = 1;</script>
<style>.a { color: red; }</style>
<h1>Hello World</h1>
<p>Some paragraph text.</p>
</body>
</html>
"""


def test_fetch_and_parse_extracts_expected_fields():
    with patch("scraper.fetch.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = SAMPLE_HTML
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        html = fetch("https://example.com/test")
        result = parse(html)

    mock_get.assert_called_once()
    assert result["title"] == "Test Page"
    assert "Hello World" in result["text"]
    assert "Some paragraph text." in result["text"]
    assert "var x = 1" not in result["text"]
    assert "color: red" not in result["text"]


def test_parse_handles_missing_title():
    result = parse("<html><body><p>No title here.</p></body></html>")
    assert result["title"] == ""
    assert "No title here." in result["text"]
