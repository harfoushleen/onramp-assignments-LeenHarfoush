"""Manual RAG demo: run a real question through answer_query() against
whatever has actually been crawled/processed/embedded, and print the answer
plus its numbered sources. For eyeballing retrieval quality and citation
correctness before the API endpoint (next task) wraps this.

Requires a real Postgres (with embedded chunks already in it, i.e. the
crawl -> process -> embed pipeline has run) and a real Ollama serving both
nomic-embed-text and llama3.2:3b.

Run with: python -m scraper.demo_rag "What is the price of A Light in the Attic?"
"""

import sys

from scraper.db import get_engine, get_session_factory
from scraper.rag import answer_query

DEFAULT_QUERY = "What products are available and what do they cost?"


def main() -> None:
    query = " ".join(sys.argv[1:]) or DEFAULT_QUERY
    session = get_session_factory(get_engine())()
    try:
        result = answer_query(session, query)
    finally:
        session.close()

    print(f"Query: {query}\n")
    print("Answer:")
    print(result.answer)
    print()
    if result.sources:
        print("Sources:")
        for source in result.sources:
            print(f"  [{source.citation}] {source.url}")
    else:
        print("Sources: (none)")


if __name__ == "__main__":
    main()
