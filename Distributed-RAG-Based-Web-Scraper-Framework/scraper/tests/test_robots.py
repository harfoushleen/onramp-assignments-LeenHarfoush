from io import BytesIO
from unittest.mock import patch

from scraper.robots import RobotsChecker

ROBOTS_TXT = b"User-agent: *\nDisallow: /admin/\nAllow: /\n"


def test_can_fetch_allows_paths_not_disallowed():
    with patch("urllib.request.urlopen", return_value=BytesIO(ROBOTS_TXT)):
        checker = RobotsChecker()
        assert checker.can_fetch("https://example.com/public/page") is True


def test_can_fetch_blocks_disallowed_paths():
    with patch("urllib.request.urlopen", return_value=BytesIO(ROBOTS_TXT)):
        checker = RobotsChecker()
        assert checker.can_fetch("https://example.com/admin/secret") is False


def test_robots_txt_is_fetched_once_per_domain():
    with patch("urllib.request.urlopen", return_value=BytesIO(ROBOTS_TXT)) as mock_urlopen:
        checker = RobotsChecker()
        checker.can_fetch("https://example.com/a")
        checker.can_fetch("https://example.com/b")
        checker.can_fetch("https://example.com/admin/c")

    mock_urlopen.assert_called_once()


def test_missing_robots_txt_allows_everything():
    """A 404 on /robots.txt (e.g. quotes.toscrape.com) means no restrictions apply."""
    from urllib.error import HTTPError

    with patch(
        "urllib.request.urlopen",
        side_effect=HTTPError("https://example.com/robots.txt", 404, "Not Found", {}, None),
    ):
        checker = RobotsChecker()
        assert checker.can_fetch("https://example.com/anything") is True
