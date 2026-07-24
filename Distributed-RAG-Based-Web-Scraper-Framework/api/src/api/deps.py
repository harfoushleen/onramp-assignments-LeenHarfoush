"""DB session wiring for FastAPI dependency injection. Reuses scraper.db's
engine/session-factory helpers directly (this is the whole point of
depending on scraper as a library -- see DECISIONS.md) rather than
re-declaring connection setup here.
"""

from collections.abc import Generator

from scraper.db import get_engine, get_session_factory, init_db
from sqlalchemy.orm import Session

_engine = get_engine()
_session_factory = get_session_factory(_engine)


def init_database() -> None:
    """Ensures the pgvector extension and all tables exist. Called once at
    API startup (see main.py's lifespan) -- idempotent, so it's harmless if
    the scraper worker already created everything, and necessary if the API
    is ever the first thing to touch a fresh database (e.g. in tests).
    """
    init_db(_engine)


def get_db() -> Generator[Session, None, None]:
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()
