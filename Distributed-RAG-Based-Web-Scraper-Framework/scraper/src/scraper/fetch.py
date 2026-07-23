"""Plain HTTP fetch with a timeout and a descriptive identifying User-Agent."""

import requests

DEFAULT_TIMEOUT_SECONDS = 10
USER_AGENT = "rag-scraper-bot/0.1 (student project; contact: harfoushleen@gmail.com)"

# HTTP statuses worth retrying: 429 (rate limited -- the site is asking us to
# slow down, not refusing outright) and any 5xx (server-side, may well be
# transient). Any other 4xx (404, 403, 401, ...) means the request itself is
# the problem -- the same URL will fail the same way next time, so retrying
# just wastes a worker slot and delays landing in the dead-letter table.
RETRYABLE_STATUS_CODES = {429, *range(500, 600)}


class FetchError(Exception):
    """A fetch failed in a way that won't be fixed by retrying: a permanent
    4xx (other than 429), a malformed URL, too many redirects, etc.
    """


class RetryableFetchError(FetchError):
    """A fetch failed in a way that might succeed on a later attempt: a
    network timeout, a connection error, or a 429/5xx HTTP response.
    """


def fetch(url: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        response.raise_for_status()
    except (requests.Timeout, requests.ConnectionError) as exc:
        raise RetryableFetchError(f"failed to fetch {url}: {exc}") from exc
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        error_cls = RetryableFetchError if status_code in RETRYABLE_STATUS_CODES else FetchError
        raise error_cls(f"failed to fetch {url}: {exc}") from exc
    except requests.RequestException as exc:
        raise FetchError(f"failed to fetch {url}: {exc}") from exc
    return response.text
