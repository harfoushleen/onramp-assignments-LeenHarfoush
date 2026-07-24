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

    # requests only trusts an explicit charset in the Content-Type header;
    # if the server omits one (both books.toscrape.com and
    # quotes.toscrape.com send `Content-Type: text/html` with no charset),
    # it silently falls back to ISO-8859-1 per an old RFC 2616 default --
    # even though the actual bytes are UTF-8, which is what these sites (and
    # most modern sites) actually send. Decoding UTF-8 bytes as Latin-1
    # doesn't raise an error, it just produces mojibake (e.g. "£" -> "Â£"),
    # so this has to be corrected explicitly. Checking the raw header for a
    # `charset` param (rather than checking response.encoding's already-
    # resolved value) is deliberate: a resolved value of "ISO-8859-1" is
    # ambiguous -- it's what requests defaults to when nothing is declared,
    # but it's also a value a server could declare on purpose, which
    # shouldn't be second-guessed. Only the undeclared case gets
    # response.apparent_encoding's real sniff of the body's actual bytes
    # (via charset_normalizer).
    if "charset" not in response.headers.get("Content-Type", "").lower():
        response.encoding = response.apparent_encoding
    return response.text
