"""Plain HTTP fetch with a timeout and a descriptive identifying User-Agent."""

import requests

DEFAULT_TIMEOUT_SECONDS = 10
USER_AGENT = "rag-scraper-bot/0.1 (student project; contact: harfoushleen@gmail.com)"


class FetchError(Exception):
    pass


def fetch(url: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise FetchError(f"failed to fetch {url}: {exc}") from exc
    return response.text
