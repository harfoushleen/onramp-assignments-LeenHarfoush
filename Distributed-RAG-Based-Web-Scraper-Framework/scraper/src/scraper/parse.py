"""Extract title and main text content from a raw HTML page."""

from bs4 import BeautifulSoup


def parse(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style"]):
        tag.decompose()

    title = soup.title.get_text(strip=True) if soup.title else ""
    body = soup.body or soup
    text = " ".join(body.get_text(separator=" ").split())

    return {"title": title, "text": text}
