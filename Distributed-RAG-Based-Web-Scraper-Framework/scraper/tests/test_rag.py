"""Unit tests for answer_query()'s citation numbering and multi-source
composition. retrieve_chunks() and generate_answer() are both mocked here
-- retrieval's actual ranking behavior is covered by test_retrieve.py's
real-pgvector tests, and generate_answer() is an external Ollama call --
so this only tests the "retrieved chunks in, labeled sources + prompt out"
wiring that's specific to rag.py.
"""

from unittest.mock import patch

from scraper.rag import NO_CONTENT_ANSWER, answer_query
from scraper.retrieve import RetrievedChunk


def _chunk(chunk_id, page_id, url, text, index=0, distance=0.1) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        page_id=page_id,
        url=url,
        chunk_text=text,
        chunk_index=index,
        distance=distance,
    )


def test_answer_query_assigns_one_citation_per_source_url():
    # Two chunks share a URL (page_id=1) and should collapse to one
    # citation number; the third, different-URL chunk gets the next one.
    chunks = [
        _chunk(1, 1, "https://example.com/a", "fact one"),
        _chunk(2, 1, "https://example.com/a", "fact one continued"),
        _chunk(3, 2, "https://example.com/b", "fact two"),
    ]

    with (
        patch("scraper.rag.retrieve_chunks", return_value=chunks),
        patch(
            "scraper.rag.generate_answer", return_value="Answer citing [1] and [2]."
        ) as mock_generate,
    ):
        result = answer_query(session=None, query="q")

    assert [s.citation for s in result.sources] == [1, 2]
    assert [s.url for s in result.sources] == ["https://example.com/a", "https://example.com/b"]
    assert result.answer == "Answer citing [1] and [2]."

    context_blocks = mock_generate.call_args.args[1]
    assert context_blocks[0].startswith("[1] ")
    assert context_blocks[1].startswith("[1] ")
    assert context_blocks[2].startswith("[2] ")


def test_answer_query_supports_multi_source_synthesis():
    chunks = [
        _chunk(1, 1, "https://example.com/a", "fact from page a"),
        _chunk(2, 2, "https://example.com/b", "fact from page b"),
    ]

    with (
        patch("scraper.rag.retrieve_chunks", return_value=chunks),
        patch("scraper.rag.generate_answer", return_value="Combined answer [1][2]."),
    ):
        result = answer_query(session=None, query="combine a and b")

    assert {s.url for s in result.sources} == {"https://example.com/a", "https://example.com/b"}
    assert len(result.sources) == 2


def test_answer_query_returns_graceful_message_with_no_retrieved_chunks():
    with (
        patch("scraper.rag.retrieve_chunks", return_value=[]),
        patch("scraper.rag.generate_answer") as mock_generate,
    ):
        result = answer_query(session=None, query="anything")

    assert result.answer == NO_CONTENT_ANSWER
    assert result.sources == []
    mock_generate.assert_not_called()


def test_answer_query_passes_k_through_to_retrieval():
    with (
        patch("scraper.rag.retrieve_chunks", return_value=[]) as mock_retrieve,
        patch("scraper.rag.generate_answer"),
    ):
        answer_query(session=None, query="q", k=10)

    mock_retrieve.assert_called_once_with(None, "q", k=10)
