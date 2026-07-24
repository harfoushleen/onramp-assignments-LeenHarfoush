"""The RAG answer flow: retrieve relevant chunks, ground a prompt in them,
generate an answer, and package it with citations back to source URLs.

A plain function (`answer_query`), not a Celery task (Day 4 task 2,
requirement 5) -- answering a query is a synchronous request/response
operation the upcoming API endpoint calls directly and waits on, not
fire-and-forget background work like crawling/processing/embedding a page.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from scraper.generate import generate_answer
from scraper.retrieve import DEFAULT_K, RetrievedChunk, retrieve_chunks

NO_CONTENT_ANSWER = (
    "No relevant content has been indexed yet, so I can't answer this from the scraped sources."
)


@dataclass
class Source:
    citation: int
    url: str
    chunk_text: str


@dataclass
class RagAnswer:
    answer: str
    sources: list[Source]


def _label_sources(chunks: list[RetrievedChunk]) -> tuple[list[Source], dict[int, int]]:
    """Assigns citation numbers 1..N to each *URL*, not each chunk, in the
    order it first appears among the retrieved chunks (closest match
    first -- retrieve_chunks() already orders by distance). Two chunks from
    the same page share one citation number, since they're the same source;
    a query whose top-k results span multiple pages naturally ends up with
    multiple citation numbers, which is what lets the generated answer cite
    more than one source (requirement 4). Returns the ordered source list
    plus a chunk_id -> citation number map, used to label each chunk's
    context block for the prompt so the model's bracketed citations line up
    with the returned sources.
    """
    sources: list[Source] = []
    url_to_citation: dict[str, int] = {}
    chunk_citation: dict[int, int] = {}
    for chunk in chunks:
        citation = url_to_citation.get(chunk.url)
        if citation is None:
            citation = len(sources) + 1
            url_to_citation[chunk.url] = citation
            sources.append(Source(citation=citation, url=chunk.url, chunk_text=chunk.chunk_text))
        chunk_citation[chunk.chunk_id] = citation
    return sources, chunk_citation


def answer_query(session: Session, query: str, k: int = DEFAULT_K) -> RagAnswer:
    """Retrieves the k most relevant chunks for `query`, asks the LLM to
    answer using only those chunks, and returns the answer alongside the
    numbered source list its citations refer back to.
    """
    chunks = retrieve_chunks(session, query, k=k)
    if not chunks:
        return RagAnswer(answer=NO_CONTENT_ANSWER, sources=[])

    sources, chunk_citation = _label_sources(chunks)
    context_blocks = [f"[{chunk_citation[chunk.chunk_id]}] {chunk.chunk_text}" for chunk in chunks]
    answer = generate_answer(query, context_blocks)
    return RagAnswer(answer=answer, sources=sources)
