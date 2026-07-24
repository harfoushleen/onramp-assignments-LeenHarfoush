from unittest.mock import patch

from scraper.rag import RagAnswer, Source


def test_ask_returns_answer_with_multi_source_citations(client, fake_session):
    rag_answer = RagAnswer(
        answer="The Great Gatsby costs £10.00 [1] and The Hobbit costs £12.50 [2].",
        sources=[
            Source(citation=1, url="https://example.com/gatsby", chunk_text="Gatsby: £10.00"),
            Source(citation=2, url="https://example.com/hobbit", chunk_text="Hobbit: £12.50"),
        ],
    )

    with patch("api.main.answer_query", return_value=rag_answer) as mock_answer_query:
        response = client.post("/ask", json={"query": "compare prices", "k": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == rag_answer.answer
    assert len(body["sources"]) == 2
    assert {s["url"] for s in body["sources"]} == {
        "https://example.com/gatsby",
        "https://example.com/hobbit",
    }
    mock_answer_query.assert_called_once_with(fake_session, "compare prices", k=5)


def test_ask_uses_default_k_when_omitted(client, fake_session):
    with patch(
        "api.main.answer_query", return_value=RagAnswer(answer="no sources", sources=[])
    ) as mock_answer_query:
        client.post("/ask", json={"query": "anything"})

    mock_answer_query.assert_called_once_with(fake_session, "anything", k=5)


def test_ask_rejects_empty_query(client):
    response = client.post("/ask", json={"query": ""})
    assert response.status_code == 422


def test_ask_rejects_missing_query(client):
    response = client.post("/ask", json={})
    assert response.status_code == 422
