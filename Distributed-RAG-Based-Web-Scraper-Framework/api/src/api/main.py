"""FastAPI app: raw/processed data access, keyword + semantic search, and
the grounded Q&A endpoint -- wraps scraper's db models, retrieve.py, and
rag.py directly (Day 4 API task; see DECISIONS.md for the api-depends-on-
scraper-as-a-library decision this relies on).
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import requests
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from scraper.db import Page, ProcessedPage, latest_page_ids_subquery
from scraper.rag import answer_query
from scraper.retrieve import DEFAULT_K, retrieve_chunks
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.deps import get_db, init_database
from api.schemas import (
    AskRequest,
    AskResponse,
    AskSource,
    ErrorResponse,
    KeywordSearchResponse,
    KeywordSearchResult,
    PageDetail,
    PageListResponse,
    PageSummary,
    ProcessedPageDetail,
    ProcessedPageListResponse,
    ProcessedPageSummary,
    SemanticSearchResponse,
    SemanticSearchResult,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_database()
    yield


app = FastAPI(title="RAG Scraper API", lifespan=lifespan)


@app.exception_handler(SQLAlchemyError)
def handle_database_error(request, exc: SQLAlchemyError) -> JSONResponse:
    """A DB-down/connection-dropped failure should look like a clean 503 to
    the caller, not a raw SQLAlchemy stack trace (requirement 4). The real
    exception is still logged server-side for debugging.
    """
    logger.exception("database error handling %s %s", request.method, request.url)
    return JSONResponse(
        status_code=503,
        content=ErrorResponse(detail="database is currently unavailable").model_dump(),
    )


@app.exception_handler(requests.exceptions.RequestException)
def handle_upstream_error(request, exc: requests.exceptions.RequestException) -> JSONResponse:
    """Both embed_text() and generate_answer() call Ollama over HTTP via
    `requests` -- an Ollama-down/timeout failure surfaces here as a clean
    503 instead of a raw connection-error trace (requirement 4).
    """
    logger.exception("upstream Ollama error handling %s %s", request.method, request.url)
    return JSONResponse(
        status_code=503,
        content=ErrorResponse(
            detail="the embedding/answer-generation service is currently unavailable"
        ).model_dump(),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/pages", response_model=PageListResponse)
def list_pages(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db),
) -> PageListResponse:
    """Raw scraped data, newest crawl first. Every version of every page is
    listed (not just the latest per url) -- this is meant to expose the
    versioned crawl history Day 3 built, not just current state.
    """
    total = session.query(Page).count()
    rows = (
        session.query(Page)
        .order_by(Page.fetched_at.desc(), Page.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [PageSummary.model_validate(row) for row in rows]
    return PageListResponse(items=items, limit=limit, offset=offset, total=total)


@app.get("/pages/{page_id}", response_model=PageDetail)
def get_page(page_id: int, session: Session = Depends(get_db)) -> PageDetail:
    page = session.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail=f"page {page_id} not found")
    return PageDetail.model_validate(page)


@app.get("/processed-pages", response_model=ProcessedPageListResponse)
def list_processed_pages(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db),
) -> ProcessedPageListResponse:
    total = session.query(ProcessedPage).count()
    rows = (
        session.query(ProcessedPage)
        .order_by(ProcessedPage.processed_at.desc(), ProcessedPage.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [ProcessedPageSummary.model_validate(row) for row in rows]
    return ProcessedPageListResponse(items=items, limit=limit, offset=offset, total=total)


@app.get("/processed-pages/{processed_page_id}", response_model=ProcessedPageDetail)
def get_processed_page(
    processed_page_id: int, session: Session = Depends(get_db)
) -> ProcessedPageDetail:
    processed_page = session.get(ProcessedPage, processed_page_id)
    if processed_page is None:
        raise HTTPException(
            status_code=404, detail=f"processed page {processed_page_id} not found"
        )
    return ProcessedPageDetail.model_validate(processed_page)


def _snippet(text: str, query: str, context_chars: int = 80) -> str:
    """A short excerpt around the first match, for keyword search results
    -- so a caller sees *why* a page matched instead of just its id/url.
    """
    index = text.lower().find(query.lower())
    if index == -1:
        return text[: context_chars * 2]
    start = max(0, index - context_chars)
    end = min(len(text), index + len(query) + context_chars)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


@app.get("/search/keyword", response_model=KeywordSearchResponse)
def search_keyword(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_db),
) -> KeywordSearchResponse:
    """Plain ILIKE substring search over each url's latest processed text,
    not Postgres full-text search (tsvector/GIN index) -- this project's
    corpus is a few hundred pages, well within the range where ILIKE is
    fast enough and trivially correct; a tsvector column plus GIN index
    would be real schema/maintenance overhead this data volume doesn't
    justify. Restricted to the latest version per url via
    latest_page_ids_subquery() (db.py) for the same reason retrieve.py
    is: an old, re-crawled version of a page shouldn't show up as a
    duplicate/stale match alongside its current version.
    """
    latest_page_ids = latest_page_ids_subquery()
    pattern = f"%{q}%"
    rows = (
        session.query(ProcessedPage, Page.url)
        .join(Page, ProcessedPage.page_id == Page.id)
        .filter(ProcessedPage.page_id.in_(latest_page_ids))
        .filter(ProcessedPage.text.ilike(pattern))
        .limit(limit)
        .all()
    )
    results = [
        KeywordSearchResult(page_id=processed.page_id, url=url, snippet=_snippet(processed.text, q))
        for processed, url in rows
    ]
    return KeywordSearchResponse(query=q, results=results)


@app.get("/search/semantic", response_model=SemanticSearchResponse)
def search_semantic(
    q: str = Query(..., min_length=1),
    k: int = Query(DEFAULT_K, ge=1, le=20),
    session: Session = Depends(get_db),
) -> SemanticSearchResponse:
    """Embeds `q` and returns the k closest chunks by pgvector cosine
    distance -- a thin HTTP wrapper around retrieve_chunks() (retrieve.py),
    reused directly rather than re-implemented here.
    """
    chunks = retrieve_chunks(session, q, k=k)
    results = [
        SemanticSearchResult(
            chunk_id=chunk.chunk_id,
            page_id=chunk.page_id,
            url=chunk.url,
            chunk_text=chunk.chunk_text,
            distance=chunk.distance,
        )
        for chunk in chunks
    ]
    return SemanticSearchResponse(query=q, results=results)


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest, session: Session = Depends(get_db)) -> AskResponse:
    """Grounded question-answering: wraps answer_query() (rag.py) directly.
    The response's `sources` are the same citation-numbered source list
    answer_query() builds -- the bracketed numbers in `answer` refer back
    to these urls.
    """
    result = answer_query(session, request.query, k=request.k)
    sources = [
        AskSource(citation=source.citation, url=source.url, chunk_text=source.chunk_text)
        for source in result.sources
    ]
    return AskResponse(answer=result.answer, sources=sources)
