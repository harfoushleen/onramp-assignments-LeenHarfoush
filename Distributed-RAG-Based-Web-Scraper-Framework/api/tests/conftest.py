"""Shared fixtures for API tests: a TestClient with get_db() overridden to
a MagicMock session, so most endpoint tests never touch a real database --
same style as the scraper package's own tests (mock the session, assert on
what was queried/returned; see scraper/tests/test_tasks.py).

TestClient(app) is instantiated *without* the `with` context-manager form,
matching test_smoke.py's existing pattern -- that avoids running the app's
lifespan (which calls init_database(), a real DB connection) during tests
that only need a mocked session.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.deps import get_db
from api.main import app


@pytest.fixture
def fake_session():
    return MagicMock()


@pytest.fixture
def client(fake_session):
    app.dependency_overrides[get_db] = lambda: fake_session
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()
