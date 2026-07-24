"""Answer-generation step: a grounded chat completion via Ollama.

llama3.2:3b, not the 1b variant or a larger 7B-class model -- chosen with
the user for CPU-only inference at this project's scale: 3b is markedly
better than 1b at strictly following "answer only from this context, cite
your sources" instructions (a real risk for citation accuracy at 1b), while
staying fast enough on CPU that a 7B-class model's slower inference isn't
worth its quality gain for a grounded-Q&A use case (not open-ended chat).
"""

import os

import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
GENERATION_MODEL = os.environ.get("OLLAMA_GENERATION_MODEL", "llama3.2:3b")

# Generous: CPU inference for a few hundred tokens of context plus the
# answer itself can take several seconds, and a cold model (not yet loaded
# into memory) adds more on top of that.
GENERATE_TIMEOUT_SECONDS = 120

SYSTEM_PROMPT = (
    "You are a question-answering assistant. Answer the user's question "
    "using ONLY the numbered sources provided below -- do not use any "
    "outside knowledge. Every claim you make must be immediately followed "
    "by the bracketed number(s) of the source(s) it came from, e.g. "
    "'The price is £51.77 [1].' If the sources don't contain enough "
    "information to answer the question, say so plainly instead of "
    "guessing."
)


def generate_answer(query: str, context_blocks: list[str]) -> str:
    """Generates a grounded answer to `query`. `context_blocks` are
    pre-formatted, pre-numbered source excerpts (see rag.py) -- this
    function only assembles them into a prompt and calls the model, it
    doesn't decide numbering or deduplication itself.
    """
    context = "\n\n".join(context_blocks)
    prompt = f"Sources:\n{context}\n\nQuestion: {query}"
    response = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": GENERATION_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        },
        timeout=GENERATE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]
