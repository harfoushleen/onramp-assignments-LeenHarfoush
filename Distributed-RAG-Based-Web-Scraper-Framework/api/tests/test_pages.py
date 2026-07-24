from datetime import UTC, datetime
from unittest.mock import MagicMock


def _fake_page(id=1, url="https://example.com", **overrides):
    defaults = dict(
        id=id,
        url=url,
        content_hash="hash",
        fetched_at=datetime.now(UTC),
        raw_html="<html></html>",
        extracted_text="text",
    )
    defaults.update(overrides)
    return MagicMock(**defaults)


def test_list_pages_returns_paginated_summaries(client, fake_session):
    pages = [_fake_page(id=1), _fake_page(id=2)]
    fake_session.query.return_value.count.return_value = 2
    chain = fake_session.query.return_value.order_by.return_value.offset.return_value
    chain.limit.return_value.all.return_value = pages

    response = client.get("/pages?limit=2&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert [item["id"] for item in body["items"]] == [1, 2]


def test_list_pages_rejects_out_of_range_limit(client):
    response = client.get("/pages?limit=0")
    assert response.status_code == 422


def test_get_page_returns_full_detail(client, fake_session):
    fake_session.get.return_value = _fake_page(id=7, extracted_text="hello world")

    response = client.get("/pages/7")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 7
    assert body["extracted_text"] == "hello world"
    assert body["raw_html"] == "<html></html>"


def test_get_page_returns_404_when_missing(client, fake_session):
    fake_session.get.return_value = None

    response = client.get("/pages/999")

    assert response.status_code == 404
    assert "999" in response.json()["detail"]
