"""Storage layer: SQLAlchemy model + engine/session helpers for the raw pages table.

`url` is intentionally not unique — this table is an append-only crawl log so that
Day 3's versioning work (keep history instead of overwriting) doesn't need a schema
change later. For now each crawl just adds a new row.
"""

import os
from datetime import datetime

from sqlalchemy import JSON, DateTime, Engine, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DEFAULT_DATABASE_URL = "postgresql+psycopg://rag:rag@localhost:5432/rag_scraper"


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


def get_engine(database_url: str | None = None) -> Engine:
    return create_engine(database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))


def init_db(engine: Engine) -> None:
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
