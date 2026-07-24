"""Pydantic response/request models for every endpoint -- FastAPI's
standard pattern, giving typed, self-documenting responses on the
automatic /docs page (Day 4 API task, requirement 3).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    content_hash: str
    fetched_at: datetime


class PageDetail(PageSummary):
    raw_html: str
    extracted_text: str


class PageListResponse(BaseModel):
    items: list[PageSummary]
    limit: int
    offset: int
    total: int


class ProcessedPageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_id: int
    processed_at: datetime


class ProcessedPageDetail(ProcessedPageSummary):
    text: str
    tables: list[dict[str, str]]


class ProcessedPageListResponse(BaseModel):
    items: list[ProcessedPageSummary]
    limit: int
    offset: int
    total: int


class KeywordSearchResult(BaseModel):
    page_id: int
    url: str
    snippet: str


class KeywordSearchResponse(BaseModel):
    query: str
    results: list[KeywordSearchResult]


class SemanticSearchResult(BaseModel):
    chunk_id: int
    page_id: int
    url: str
    chunk_text: str
    distance: float


class SemanticSearchResponse(BaseModel):
    query: str
    results: list[SemanticSearchResult]


class AskRequest(BaseModel):
    query: str = Field(min_length=1)
    k: int = Field(default=5, ge=1, le=20)


class AskSource(BaseModel):
    citation: int
    url: str
    chunk_text: str


class AskResponse(BaseModel):
    answer: str
    sources: list[AskSource]


class ErrorResponse(BaseModel):
    detail: str
