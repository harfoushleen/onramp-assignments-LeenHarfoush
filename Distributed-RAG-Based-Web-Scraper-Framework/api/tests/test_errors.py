"""A DB-down or Ollama-down failure should reach the caller as a clean,
typed error response -- not a raw stack trace (Day 4 API task,
requirement 4). Covers the two exception handlers registered in main.py.
"""

from unittest.mock import patch

import requests
from sqlalchemy.exc import OperationalError


def test_database_error_returns_clean_503_not_a_stack_trace(client, fake_session):
    fake_session.query.side_effect = OperationalError("stmt", {}, Exception("connection refused"))

    response = client.get("/pages")

    assert response.status_code == 503
    body = response.json()
    assert list(body.keys()) == ["detail"]
    assert "database" in body["detail"].lower()


def test_upstream_ollama_error_returns_clean_503_not_a_stack_trace(client):
    with patch(
        "api.main.retrieve_chunks",
        side_effect=requests.exceptions.ConnectionError("connection refused"),
    ):
        response = client.get("/search/semantic?q=test")

    assert response.status_code == 503
    body = response.json()
    assert list(body.keys()) == ["detail"]
    assert "unavailable" in body["detail"].lower()
