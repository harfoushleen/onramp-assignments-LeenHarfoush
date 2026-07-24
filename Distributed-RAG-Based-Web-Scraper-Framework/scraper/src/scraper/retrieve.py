"""Retrieval step: given a natural-language query, embeds it with the same
Ollama model used to embed chunks (embed.py), then finds the most similar
chunks in Postgres via pgvector cosine distance.

Only searches chunks belonging to each URL's most recently crawled page
version. `pages` keeps every version of a page rather than overwriting
(Day 3's versioning decision), and `chunks.page_id` points at a specific
version -- without this filter, a URL that's been re-crawled multiple times
could surface a stale chunk from an old version alongside (or instead of)
its current one, or the same fact could appear to come from "two sources"
that are really just two versions of one page. This mirrors
get_latest_page()/get_latest_processed_page()'s "current version is a
query, not a stored flag" approach (db.py), just computed across every URL
at once via a window function instead of one URL at a time.

Not capped per-URL beyond that: if the k closest chunks legitimately span
multiple different pages, all of them come back -- there's no "one chunk
per page" restriction here, which is what lets answer_query() (rag.py)
synthesize an answer from more than one source (Day 4 task 2, requirement 4).
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from scraper.db import Chunk, Page, latest_page_ids_subquery
from scraper.embed import embed_text

DEFAULT_K = 5


@dataclass
class RetrievedChunk:
    chunk_id: int
    page_id: int
    url: str
    chunk_text: str
    chunk_index: int
    distance: float


def retrieve_chunks(session: Session, query: str, k: int = DEFAULT_K) -> list[RetrievedChunk]:
    """Embeds `query` and returns the k chunks with the smallest cosine
    distance to it (closest match first), restricted to each url's latest
    version -- see db.latest_page_ids_subquery()'s docstring.
    """
    query_embedding = embed_text(query)
    latest_page_ids = latest_page_ids_subquery()
    distance = Chunk.embedding.cosine_distance(query_embedding).label("distance")
    rows = (
        session.query(Chunk, Page.url, distance)
        .join(Page, Chunk.page_id == Page.id)
        .filter(Chunk.page_id.in_(latest_page_ids))
        .order_by(distance)
        .limit(k)
        .all()
    )
    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            page_id=chunk.page_id,
            url=url,
            chunk_text=chunk.chunk_text,
            chunk_index=chunk.chunk_index,
            distance=float(dist),
        )
        for chunk, url, dist in rows
    ]
