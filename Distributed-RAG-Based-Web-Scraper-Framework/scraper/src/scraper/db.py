"""Storage layer: SQLAlchemy model + engine/session helpers for the raw pages table.

`url` is intentionally not unique — this table is an append-only crawl log so that
Day 3's versioning work (keep history instead of overwriting) doesn't need a schema
change later. For now each crawl just adds a new row.
"""

import os
from datetime import datetime

from sqlalchemy import DateTime, Engine, Integer, String, Text, create_engine
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


def get_engine(database_url: str | None = None) -> Engine:
    return create_engine(database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine)
