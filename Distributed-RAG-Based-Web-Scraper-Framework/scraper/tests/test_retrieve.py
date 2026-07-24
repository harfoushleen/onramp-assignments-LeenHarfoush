"""Integration tests for retrieve_chunks() against a real Postgres +
pgvector -- opt-in (RUN_DB_TESTS=1) since, unlike the rest of this test
suite, they need a real database reachable via DATABASE_URL (matching the
`browser` marker's pattern in test_fetch_js.py for real-dependency tests
that don't run by default or in CI).

embed_text() is still mocked -- no real Ollama needed here. These tests are
about pgvector's cosine-distance ranking and the latest-version-only
filter, not about embedding quality; hand-crafted vectors make the expected
ranking exact and deterministic instead of depending on what a real
embedding model happens to produce for a given string.

Each test runs inside one uncommitted transaction (insert -> query -> roll
back), so nothing written here persists in a real dev/demo database.
"""

import os
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from scraper.db import Chunk, Page, get_engine, get_session_factory, init_db
from scraper.retrieve import retrieve_chunks

EMBEDDING_DIM = 768

requires_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 (with a real Postgres+pgvector via DATABASE_URL) to run these",
)


def _vector(*nonzero_at: tuple[int, float]) -> list[float]:
    vec = [0.0] * EMBEDDING_DIM
    for index, value in nonzero_at:
        vec[index] = value
    return vec


@pytest.fixture
def db_session():
    engine = get_engine()
    init_db(engine)
    session = get_session_factory(engine)()
    yield session
    session.rollback()
    session.close()


def _make_page(session, url: str) -> Page:
    page = Page(
        url=url,
        raw_html="<html></html>",
        extracted_text="text",
        content_hash="hash",
        fetched_at=datetime.now(UTC),
    )
    session.add(page)
    session.flush()
    return page


def _make_chunk(session, page: Page, text: str, embedding: list[float], index: int = 0) -> Chunk:
    chunk = Chunk(
        page_id=page.id,
        chunk_text=text,
        embedding=embedding,
        chunk_index=index,
        created_at=datetime.now(UTC),
    )
    session.add(chunk)
    session.flush()
    return chunk


@pytest.mark.db
@requires_db
def test_retrieve_chunks_returns_closest_match_first(db_session):
    close_page = _make_page(db_session, "https://example.com/close")
    far_page = _make_page(db_session, "https://example.com/far")
    close_chunk = _make_chunk(db_session, close_page, "relevant content", _vector((0, 1.0)))
    _make_chunk(db_session, far_page, "irrelevant content", _vector((1, 1.0)))

    query_vector = _vector((0, 1.0))
    with patch("scraper.retrieve.embed_text", return_value=query_vector):
        results = retrieve_chunks(db_session, "what is relevant?", k=1)

    assert len(results) == 1
    assert results[0].chunk_id == close_chunk.id
    assert results[0].url == "https://example.com/close"


@pytest.mark.db
@requires_db
def test_retrieve_chunks_only_searches_latest_page_version(db_session):
    old_page = _make_page(db_session, "https://example.com/versioned")
    new_page = _make_page(db_session, "https://example.com/versioned")
    stale_chunk = _make_chunk(db_session, old_page, "stale content", _vector((0, 1.0)))
    fresh_chunk = _make_chunk(db_session, new_page, "fresh content", _vector((0, 1.0)))

    query_vector = _vector((0, 1.0))
    with patch("scraper.retrieve.embed_text", return_value=query_vector):
        results = retrieve_chunks(db_session, "irrelevant query text", k=5)

    result_ids = {r.chunk_id for r in results}
    assert fresh_chunk.id in result_ids
    assert stale_chunk.id not in result_ids


@pytest.mark.db
@requires_db
def test_retrieve_chunks_can_span_multiple_pages_for_synthesis(db_session):
    page_a = _make_page(db_session, "https://example.com/a")
    page_b = _make_page(db_session, "https://example.com/b")
    _make_chunk(db_session, page_a, "fact from page a", _vector((0, 0.95), (1, 0.05)))
    _make_chunk(db_session, page_b, "fact from page b", _vector((0, 0.95), (2, 0.05)))
    _make_chunk(db_session, page_a, "unrelated content", _vector((5, 1.0)))

    query_vector = _vector((0, 1.0))
    with patch("scraper.retrieve.embed_text", return_value=query_vector):
        results = retrieve_chunks(db_session, "combine facts from a and b", k=2)

    urls = {r.url for r in results}
    assert urls == {"https://example.com/a", "https://example.com/b"}
