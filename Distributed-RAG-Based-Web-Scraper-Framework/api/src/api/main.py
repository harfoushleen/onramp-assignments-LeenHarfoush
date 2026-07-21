"""FastAPI app entry point.

Day 1: health check only. Data/search/RAG endpoints land on Day 4.
"""

from fastapi import FastAPI

app = FastAPI(title="RAG Scraper API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
