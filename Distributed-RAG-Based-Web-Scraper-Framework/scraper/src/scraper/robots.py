"""robots.txt compliance, one parser per domain, fetched and cached lazily.

Relies on urllib's built-in handling of a missing robots.txt: a 404 response is
treated as "no restrictions" (allow everything), which is the correct behavior
for sites like quotes.toscrape.com that don't publish one at all.
"""

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser


class RobotsChecker:
    def __init__(self) -> None:
        self._parsers: dict[str, RobotFileParser] = {}

    def _get_parser(self, url: str) -> RobotFileParser:
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        if domain not in self._parsers:
            parser = RobotFileParser()
            parser.set_url(f"{domain}/robots.txt")
            parser.read()
            self._parsers[domain] = parser
        return self._parsers[domain]

    def can_fetch(self, url: str, user_agent: str = "*") -> bool:
        return self._get_parser(url).can_fetch(user_agent, url)
