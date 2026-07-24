from datetime import UTC, datetime
from unittest.mock import MagicMock


def _fake_processed_page(id=1, page_id=1, **overrides):
    defaults = dict(
        id=id,
        page_id=page_id,
        processed_at=datetime.now(UTC),
        text="clean text",
        tables=[{"UPC": "abc123"}],
    )
    defaults.update(overrides)
    return MagicMock(**defaults)


def test_list_processed_pages_returns_paginated_summaries(client, fake_session):
    rows = [_fake_processed_page(id=1), _fake_processed_page(id=2)]
    fake_session.query.return_value.count.return_value = 2
    chain = fake_session.query.return_value.order_by.return_value.offset.return_value
    chain.limit.return_value.all.return_value = rows

    response = client.get("/processed-pages?limit=2&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [1, 2]


def test_get_processed_page_returns_full_detail(client, fake_session):
    fake_session.get.return_value = _fake_processed_page(
        id=3, text="A Light in the Attic", tables=[{"Price": "£51.77"}]
    )

    response = client.get("/processed-pages/3")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 3
    assert body["text"] == "A Light in the Attic"
    assert body["tables"] == [{"Price": "£51.77"}]


def test_get_processed_page_returns_404_when_missing(client, fake_session):
    fake_session.get.return_value = None

    response = client.get("/processed-pages/999")

    assert response.status_code == 404
    assert "999" in response.json()["detail"]
