"""Storage layer: SQLAlchemy model + engine/session helpers for the raw pages table.

`url` is intentionally not unique — this table is an append-only crawl log so that
Day 3's versioning work (keep history instead of overwriting) doesn't need a schema
change later. For now each crawl just adds a new row.
"""

import os
from datetime import datetime

from dotenv import load_dotenv
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    ScalarSelect,
    String,
    Text,
    create_engine,
    func,
    select,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

# Loads scraper/.env (local-dev-only overrides -- gitignored) into os.environ
# before anything below reads it. A no-op in Docker/CI, where these vars are
# already set in the real environment and no .env file exists;
# load_dotenv() never overrides a variable that's already set, so it can't
# clobber those. Called here (not just in celery_app.py) because db.py is
# imported directly by scripts/tests that never touch Celery at all.
load_dotenv()

DEFAULT_DATABASE_URL = "postgresql+psycopg://rag:rag@localhost:5432/rag_scraper"

# nomic-embed-text's output dimensionality -- fixed by the model, not
# configurable independently of it. If the embedding model ever changes,
# this (and the stored vectors) need to change together.
EMBEDDING_DIM = 768


class Base(DeclarativeBase):
    pass


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    raw_html: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProcessedPage(Base):
    """Normalized, structured output of the processing step -- kept in its own table,
    separate from `pages`, so the raw crawl log (raw_html/extracted_text) is never
    overwritten and both versions stay queryable independently.
    """

    __tablename__ = "processed_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    tables: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DeadLetterTask(Base):
    """A record of a task that exhausted its retries (or failed with a
    non-retryable error) -- so a permanently failed job lands somewhere
    visible and queryable instead of just disappearing into worker logs.
    `url` is nullable because not every task is URL-shaped (process_page_task
    only has a page_id; it's resolved back to a URL on a best-effort basis,
    see tasks.py).
    """

    __tablename__ = "dead_letter_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    error: Mapped[str] = mapped_column(Text, nullable=False)
    failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)


class Chunk(Base):
    """A single embeddable unit of a ProcessedPage: either a slice of the
    overlap-chunked body text, or one serialized table (see chunk.py). One
    ProcessedPage produces many Chunk rows, in chunk_index order.
    """

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id"), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def get_engine(database_url: str | None = None) -> Engine:
    return create_engine(database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))


def init_db(engine: Engine) -> None:
    # Must run before create_all(): the `vector` column type on Chunk only
    # exists in Postgres once this extension is enabled, so creating tables
    # first would fail on a fresh database.
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine)


def get_latest_page(session: Session, url: str) -> Page | None:
    """Returns the most recently fetched Page row for a URL, or None if it's
    never been crawled. `pages.url` is intentionally non-unique (see module
    docstring), so "current version" is a query, not a stored flag -- a flag
    column would need updating on every prior row each time a new version
    lands, whereas this is just an ORDER BY ... LIMIT 1.
    """
    return (
        session.query(Page)
        .filter(Page.url == url)
        .order_by(Page.fetched_at.desc(), Page.id.desc())
        .first()
    )


def latest_page_ids_subquery() -> ScalarSelect:
    """A scalar subquery of Page.id, one row per url, for that url's most
    recently crawled version (highest fetched_at, ties broken by id).
    `pages` keeps every version of a page rather than overwriting (Day 3's
    versioning decision), so anything that shouldn't mix stale and current
    content for the same url -- semantic retrieval (retrieve.py), keyword
    search, and any future "current state" query -- filters through this
    rather than searching every version ever crawled. Same "current version
    is a query, not a stored flag" principle as get_latest_page()/
    get_latest_processed_page() above, just computed for every url at once
    (via a ROW_NUMBER() window) instead of one url at a time, since those
    two only ever needed a single url's latest row.
    """
    row_number = (
        func.row_number()
        .over(partition_by=Page.url, order_by=(Page.fetched_at.desc(), Page.id.desc()))
        .label("rn")
    )
    ranked = select(Page.id, row_number).subquery()
    return select(ranked.c.id).where(ranked.c.rn == 1).scalar_subquery()


def get_latest_processed_page(session: Session, url: str) -> ProcessedPage | None:
    """Returns the most recently processed ProcessedPage row for a URL (joined
    through pages.url), or None if no version of that URL has been processed
    yet. Can lag behind get_latest_page() if a raw version was just stored but
    its processing task hasn't run yet -- that's expected, not a bug.
    """
    return (
        session.query(ProcessedPage)
        .join(Page, ProcessedPage.page_id == Page.id)
        .filter(Page.url == url)
        .order_by(ProcessedPage.processed_at.desc(), ProcessedPage.id.desc())
        .first()
    )
