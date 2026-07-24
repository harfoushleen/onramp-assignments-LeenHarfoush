"""Embedding client: thin wrapper around Ollama's /api/embed endpoint.

A plain `requests` call rather than an Ollama SDK dependency -- this is a
single JSON POST, and the project already depends on `requests` for fetch.py.
"""

import os

import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.environ.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")

# Generous: first-ever call on a freshly started container can block on
# Ollama finishing the model load into memory, on top of normal inference.
EMBED_TIMEOUT_SECONDS = 60


def embed_text(text: str) -> list[float]:
    """Returns the embedding vector for `text` via Ollama's embed API."""
    response = requests.post(
        f"{OLLAMA_URL}/api/embed",
        json={"model": EMBEDDING_MODEL, "input": text},
        timeout=EMBED_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()["embeddings"][0]
