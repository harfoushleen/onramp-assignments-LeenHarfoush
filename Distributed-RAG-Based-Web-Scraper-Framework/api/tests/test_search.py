from unittest.mock import MagicMock, patch

from scraper.retrieve import RetrievedChunk


def test_search_keyword_returns_snippet_matches(client, fake_session):
    processed = MagicMock(page_id=3, text="The Great Gatsby costs £10.00 today.")
    chain = fake_session.query.return_value.join.return_value.filter.return_value.filter
    chain.return_value.limit.return_value.all.return_value = [
        (processed, "https://example.com/book")
    ]

    response = client.get("/search/keyword?q=Gatsby")

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "Gatsby"
    assert len(body["results"]) == 1
    assert body["results"][0]["page_id"] == 3
    assert body["results"][0]["url"] == "https://example.com/book"
    assert "Gatsby" in body["results"][0]["snippet"]


def test_search_keyword_requires_nonempty_query(client):
    response = client.get("/search/keyword?q=")
    assert response.status_code == 422


def test_search_semantic_returns_ranked_chunks(client):
    chunks = [
        RetrievedChunk(
            chunk_id=1,
            page_id=1,
            url="https://example.com/a",
            chunk_text="fact",
            chunk_index=0,
            distance=0.1,
        )
    ]

    with patch("api.main.retrieve_chunks", return_value=chunks) as mock_retrieve:
        response = client.get("/search/semantic?q=fact&k=1")

    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["url"] == "https://example.com/a"
    assert body["results"][0]["distance"] == 0.1
    mock_retrieve.assert_called_once()
    assert mock_retrieve.call_args.args[1] == "fact"
    assert mock_retrieve.call_args.kwargs["k"] == 1


def test_search_semantic_requires_nonempty_query(client):
    response = client.get("/search/semantic?q=")
    assert response.status_code == 422
